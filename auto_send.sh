#!/bin/bash

S3_BUCKET="aws-weillington"
image_folder="/opt/advantech/web/temp_folder/project/test2/images"

rm -rf $image_folder/*

while true; do
    
    curl --location 'http://localhost:5000/fe/save_frame' --header 'Content-Type: application/json' --data '{"project_name":"test2"}'

    timestamp=$(date +%Y-%m-%d_%H-%M-%S)
    
    image_path=$(ls $image_folder | head -n 1)

    if [[ -z "$image_path" ]]; then
        echo "No image file found, skipping upload"
        continue
    fi
    image_path="$image_folder/$image_path"
    
    aws s3api put-object --bucket $S3_BUCKET --key "image_${timestamp}.jpg" --body "$image_path"

    rm "$image_path"

    image_count=$(aws s3 ls s3://$S3_BUCKET/ --recursive | wc -l)
    echo "Image count: $image_count"
    
    if [ "$image_count" -gt 100000 ]; then
        files_to_delete=$(aws s3 ls s3://$S3_BUCKET/ --recursive --query "reverse(sort_by(Contents, &LastModified))[:${image_count}-10].Key" --output text)
        
        for file in $files_to_delete; do
            echo "Deleting old file: $file"
            aws s3 rm "s3://$S3_BUCKET/$file"
        done
    fi

    sleep 60
done
