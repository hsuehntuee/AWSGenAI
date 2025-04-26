// index.mjs
import { S3Client } from "@aws-sdk/client-s3";
import { RekognitionClient, DetectLabelsCommand } from "@aws-sdk/client-rekognition";

// ✅ 建立 S3 / Rekognition 服務物件
const s3Client = new S3Client();
const rekognitionClient = new RekognitionClient();

// ✅ Lambda handler：一定要叫 handler！
export const handler = async (event) => {
  const record = event.Records?.[0];
  const bucket = record?.s3?.bucket?.name;
  const key = decodeURIComponent(record?.s3?.object?.key || "").replace(/\+/g, " ");

  console.log(`📥 收到圖片：${key} 來自 bucket：${bucket}`);

  if (!bucket || !key) {
    console.log("❌ 錯誤：沒有找到 bucket 或 key");
    return { statusCode: 400, body: "Invalid S3 event" };
  }

  // Rekognition 分析圖像內容
  try {
    const command = new DetectLabelsCommand({
      Image: {
        S3Object: { Bucket: bucket, Name: key },
      },
      MaxLabels: 10,
      MinConfidence: 70,
    });

    const response = await rekognitionClient.send(command);

    let personCount = 0;
    for (const label of response.Labels) {
      if (label.Name === "Person") {
        personCount = label.Instances.length;
        break;
      }
    }

    console.log(`👥 人數分析結果：${personCount} 人`);

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: `偵測到 ${personCount} 個人`,
        image: key,
      }),
    };
  } catch (err) {
    console.error("❌ Rekognition 錯誤：", err);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message }),
    };
  }
};
