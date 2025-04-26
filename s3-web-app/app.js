// AWS SDK 設定
AWS.config.update({
    region: 'us-west-2', // 這裡填寫你 AWS 區域 (例如 us-east-1)
    accessKeyId: 'AKIATC4PSTG5PHLPTN7C', // 用你自己的 Access Key ID
    secretAccessKey: 'kGC12JsPv4TrnTg3UpJoEzPkcVLx55+CBvCXgZWT' // 用你自己的 Secret Access Key
});

// S3 存取功能
const s3 = new AWS.S3();
const bucketName = 'aws-weillington'; // 你的 S3 桶名稱

// 當按鈕被點擊時，列出 S3 桶中的檔案
document.getElementById('load-s3').addEventListener('click', function() {
    const params = {
        Bucket: bucketName,
        MaxKeys: 10
    };

    s3.listObjectsV2(params, function(err, data) {
        if (err) {
            console.error("Error loading S3 data:", err);
            document.getElementById('s3-data').innerHTML = "Failed to load data from S3.";
        } else {
            let output = "<h3>S3 Bucket Files:</h3><ul>";
            data.Contents.forEach(function(file) {
                output += `<li>${file.Key}</li>`;
            });
            output += "</ul>";
            document.getElementById('s3-data').innerHTML = output;
        }
    });
});

// 呼叫 API Gateway 來載入 Timestream 資料
document.getElementById('load-timestream').addEventListener('click', function() {
    const apiUrl = 'https://noqawfuw7c.execute-api.us-west-2.amazonaws.com/timestream'; // TODO: 替換成你的 API URL

    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            if (data.message === 'Success') {
                let output = "<h3>Timestream Data:</h3><ul>";
                data.data.forEach(function(row) {
                    output += `<li>${row}</li>`;
                });
                output += "</ul>";
                document.getElementById('timestream-data').innerHTML = output;
            } else {
                document.getElementById('timestream-data').innerHTML = "Failed to load data from Timestream.";
            }
        })
        .catch(error => {
            console.error("Error fetching Timestream data:", error);
            document.getElementById('timestream-data').innerHTML = "Failed to load data from Timestream.";
        });
});
