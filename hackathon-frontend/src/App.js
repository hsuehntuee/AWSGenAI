// src/App.js
import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import AWS from 'aws-sdk'; // 導入 AWS SDK
import './App.css';

function App() {
  const [promptInput, setPromptInput] = useState('');
  const [aiAnswer, setAiAnswer] = useState('');
  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [errorAI, setErrorAI] = useState('');

  const [timeSeriesData, setTimeSeriesData] = useState([]);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [errorData, setErrorData] = useState('');
  const [chartType, setChartType] = useState('line');
  
  // S3 相關狀態
  const [roomImages, setRoomImages] = useState({
    RoomA: [],
    RoomB: [],
    RoomC: []
  });
  const [isLoadingS3, setIsLoadingS3] = useState(false);
  const [errorS3, setErrorS3] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [activeRoom, setActiveRoom] = useState('RoomA'); // 預設顯示 RoomA

  const AI_API_ENDPOINT_URL = 'https://io2gztmyt0.execute-api.us-west-2.amazonaws.com/ask';
  const DATA_API_ENDPOINT_URL = 'https://io2gztmyt0.execute-api.us-west-2.amazonaws.com/data';
  const bucketName = 'aws-weillington';
  const roomFolders = ['RoomA', 'RoomB', 'RoomC'];

  // 設定 AWS SDK
  useEffect(() => {
    AWS.config.update({
      region: 'us-west-2',
      accessKeyId: '',
      secretAccessKey: ''
    });
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoadingData(true);
      setErrorData('');

      try {
        const response = await fetch(DATA_API_ENDPOINT_URL, { method: 'GET' });
        if (!response.ok) {
          throw new Error(`HTTP 錯誤！ 狀態碼: ${response.status}`);
        }
        const rawData = await response.json();
        const groupedData = {};

        rawData.forEach(item => {
          const key = `${item.time}_${item.room}`;
          if (!groupedData[key]) {
            groupedData[key] = {
              time: item.time,
              room: item.room,
              peopleCount: null,
              slackingDescription: ''
            };
          }
          if (item.measureName === 'PeopleCount') {
            groupedData[key].peopleCount = item.bigintValue ?? null;
          } else if (item.measureName === 'SlackingDescription') {
            groupedData[key].slackingDescription = item.varcharValue ?? '';
          }
        });

        const formattedData = Object.values(groupedData);
        setTimeSeriesData(formattedData);
      } catch (err) {
        console.error('獲取數據錯誤:', err);
        setErrorData(`無法載入數據：${err.message}`);
        setTimeSeriesData([]);
      } finally {
        setIsLoadingData(false);
      }
    };
    fetchData();
  }, []);

  const handleSubmit = () => {
    if (!promptInput.trim()) {
      setErrorAI('請先輸入您的問題！');
      return;
    }
    setIsLoadingAI(true);
    setAiAnswer('');
    setErrorAI('');

    fetch(AI_API_ENDPOINT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_question: promptInput }),
    })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP 錯誤！ 狀態碼: ${response.status}`);
        return response.json();
      })
      .then(data => {
        if (data && data.answer) setAiAnswer(data.answer);
        else setErrorAI('從 API 回應中找不到有效的回答。');
      })
      .catch(err => {
        console.error('呼叫 AI API 錯誤:', err);
        setErrorAI(`請求失敗：${err.message}`);
      })
      .finally(() => setIsLoadingAI(false));
  };

  const toggleChartType = () => {
    setChartType((prev) => (prev === 'line' ? 'bar' : 'line'));
  };

  // 載入 S3 圖片函數
  const loadS3Images = () => {
    setIsLoadingS3(true);
    setErrorS3('');
    setSelectedImage(null);
    
    const s3 = new AWS.S3();
    const imagesByRoom = {
      RoomA: [],
      RoomB: [],
      RoomC: []
    };
    
    // 建立一個 Promise 陣列，為每個房間獲取圖片
    const promises = roomFolders.map(roomFolder => {
      const params = {
        Bucket: bucketName,
        Prefix: `${roomFolder}/`, 
        Delimiter: '/'
      };
      
      return new Promise((resolve, reject) => {
        s3.listObjectsV2(params, (err, data) => {
          if (err) {
            console.error(`Error loading ${roomFolder} data:`, err);
            reject(err);
          } else {
            // 過濾出 JPG 檔案
            const jpgFiles = (data.Contents || [])
              .filter(file => 
                (file.Key.toLowerCase().endsWith('.jpg') || file.Key.toLowerCase().endsWith('.jpeg')) &&
                file.Key !== `${roomFolder}/`
              )
              // 按最後修改時間排序（最新的在前）
              .sort((a, b) => new Date(b.LastModified) - new Date(a.LastModified));
            
            imagesByRoom[roomFolder] = jpgFiles;
            resolve();
          }
        });
      });
    });
    
    // 等待所有房間的圖片都載入完成
    Promise.all(promises)
      .then(() => {
        setRoomImages(imagesByRoom);
      })
      .catch(err => {
        setErrorS3(`無法載入 S3 數據: ${err.message}`);
      })
      .finally(() => {
        setIsLoadingS3(false);
      });
  };

  // 處理圖片點擊
  const handleImageClick = (fileKey) => {
    setSelectedImage(`https://${bucketName}.s3.${AWS.config.region}.amazonaws.com/${fileKey}`);
  };

  // 切換房間
  const handleRoomChange = (room) => {
    setActiveRoom(room);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>威靈頓牛排有限公司 邊雲智控會議室系統</h1>
        
        {/* 使用網格布局包裹所有區塊 */}
        <div className="main-grid">
          {/* AI 問答區塊 */}
          <div className="section-container ai-section">
            <h2>向 AI 提問</h2>
            <textarea
              className="input-textarea"
              rows="4"
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              placeholder="請輸入您想詢問的問題..."
              disabled={isLoadingAI}
            />
            <div style={{ marginTop: '10px' }}>
              <button className="primary-button" onClick={handleSubmit} disabled={isLoadingAI}>
                {isLoadingAI ? '正在思考中...' : '向 AI 提問'}
              </button>
            </div>
            {errorAI && <p className="error-message">{errorAI}</p>}
            {aiAnswer && (
              <div className="answer-box">
                <h3>AI 回答：</h3>
                <pre>{aiAnswer}</pre>
              </div>
            )}
          </div>
          
          {/* Timestream 數據區塊 */}
          <div className="section-container data-section">
            <h2>Timestream 數據</h2>
            
            {isLoadingData && <p>正在載入數據...</p>}
            {errorData && <p className="error-message">{errorData}</p>}

            {/* 圖表 */}
            {!isLoadingData && !errorData && timeSeriesData.length > 0 && (
              <div className="chart-section">
                <h3>人數變化圖表</h3>
                <button className="secondary-button" onClick={toggleChartType} style={{ marginBottom: '20px' }}>
                  切換成 {chartType === 'line' ? '直條圖' : '折線圖'}
                </button>
                <ResponsiveContainer width="100%" height={250}>
                  {chartType === 'line' ? (
                    <LineChart data={timeSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" tickFormatter={(t) => t.slice(11, 16)} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="peopleCount" stroke="#8884d8" activeDot={{ r: 6 }} />
                    </LineChart>
                  ) : (
                    <BarChart data={timeSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" tickFormatter={(t) => t.slice(11, 16)} />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="peopleCount" fill="#82ca9d" />
                    </BarChart>
                  )}
                </ResponsiveContainer>
              </div>
            )}

            {/* 表格 - 最多顯示5筆資料 */}
            {!isLoadingData && !errorData && timeSeriesData.length > 0 && (
              <div className="table-container">
                <h3>最近數據</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>時間</th>
                      <th>房間</th>
                      <th>人數</th>
                      <th>描述</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeSeriesData.slice(0, 5).map((data, index) => (
                      <tr key={index}>
                        <td>{data.time}</td>
                        <td>{data.room}</td>
                        <td>{data.peopleCount !== null ? data.peopleCount : 'N/A'}</td>
                        <td>{data.slackingDescription || 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {!isLoadingData && !errorData && timeSeriesData.length === 0 && (
              <p>沒有找到符合條件的數據。</p>
            )}
          </div>
          
          {/* S3 圖片瀏覽區塊 - 跨整行 */}
          <div className="section-container image-section">
            <div className="image-section-header">
              <h2>會議室圖片瀏覽</h2>
              <button 
                className="primary-button"
                onClick={loadS3Images} 
                disabled={isLoadingS3}
              >
                {isLoadingS3 ? '載入中...' : '載入會議室圖片'}
              </button>
            </div>
            
            {errorS3 && <p className="error-message">{errorS3}</p>}
            
            {isLoadingS3 && <p>正在載入會議室圖片...</p>}
            
            {!isLoadingS3 && Object.values(roomImages).some(images => images.length > 0) && (
              <div className="room-images">
                {/* 縮圖預覽區域 */}
                <div className="image-content-grid">
                  {/* 左側：各房間最新圖片 */}
                  <div className="latest-images">
                    <h3>各房間最新圖片</h3>
                    <div className="room-preview-container">
                      {roomFolders.map(room => (
                        <div key={room} className="room-preview">
                          <h4>{room}</h4>
                          <div className="preview-images">
                            {roomImages[room].slice(0, 3).map((file, index) => (
                              <div key={index} className="preview-image-container">
                                <img 
                                  src={`https://${bucketName}.s3.${AWS.config.region}.amazonaws.com/${file.Key}`} 
                                  alt={file.Key} 
                                  className="preview-image"
                                  onClick={() => handleImageClick(file.Key)}
                                />
                                <p className="image-filename">
                                  {file.Key.split('/')[1]}
                                </p>
                              </div>
                            ))}
                            {roomImages[room].length === 0 && (
                              <p className="no-images-text">此房間無圖片</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  {/* 右側：選中的圖片 */}
                  <div className="selected-image-area">
                    {selectedImage ? (
                      <div className="selected-image-container">
                        <h3>選中的圖片</h3>
                        <img 
                          src={selectedImage} 
                          alt="Selected" 
                          className="selected-image"
                        />
                      </div>
                    ) : (
                      <div className="no-selection">
                        <h3>請選擇一張圖片查看</h3>
                        <p>點擊左側圖片預覽或下方檔案名稱</p>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* 底部：圖片文件列表 */}
                <div className="room-files-area">
                  {/* 房間選擇標籤 */}
                  <div className="room-tabs">
                    {roomFolders.map(room => (
                      <button 
                        key={room}
                        onClick={() => handleRoomChange(room)}
                        className={`room-tab ${activeRoom === room ? 'active-tab' : ''}`}
                      >
                        {room}
                      </button>
                    ))}
                  </div>
                  
                  {/* 當前選擇房間的所有圖片檔案列表 */}
                  <h3>{activeRoom} 所有圖片</h3>
                  {roomImages[activeRoom].length > 0 ? (
                    <div className="file-list">
                      {roomImages[activeRoom].map((file, index) => (
                        <div 
                          key={index}
                          onClick={() => handleImageClick(file.Key)}
                          className={`file-item ${selectedImage && selectedImage.includes(file.Key) ? 'selected-file' : ''}`}
                        >
                          {file.Key.split('/')[1]}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="no-images-text">此房間無圖片</p>
                  )}
                </div>
              </div>
            )}
            
            {!isLoadingS3 && Object.values(roomImages).every(images => images.length === 0) && !errorS3 && (
              <p>尚未載入圖片或無法找到符合條件的圖片。</p>
            )}
          </div>
        </div>
      </header>
    </div>
  );
}

export default App;
