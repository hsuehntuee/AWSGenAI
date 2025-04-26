安裝 http-server：
首先，你需要安裝 Node.js，然後使用以下命令安裝 http-server：


# 安裝 http-server（如果你已經安裝了 Node.js，則可以跳過這步）

    npm install -g http-server

# 啟動伺服器：
在 s3-web-app 目錄下啟動伺服器：


    http-server

這會在 http://localhost:8080 啟動你的 Web 應用。打開瀏覽器並訪問該 URL，就能看到你的應用運行了。


# 前置作業：

請確保你有透過 npm 安裝下面這些套件：

bash
複製程式碼
npm install @aws-sdk/client-s3 @aws-sdk/client-timestream-query