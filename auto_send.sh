#!/bin/bash

S3_BUCKET="aws-weillington"
image_folder="/opt/advantech/web/temp_folder/project/test2/images"

# Clean the images folder
rm -rf $image_folder/*

while true; do
    # Capture the image by sending a POST request
    curl --location 'http://localhost:5000/fe/save_frame' --header 'Content-Type: application/json' --data '{"project_name":"test2"}'

    timestamp=$(date +%Y-%m-%d_%H-%M-%S)
    # Get the only image file from the directory
    image_path=$(ls $image_folder | head -n 1)

    if [[ -z "$image_path" ]]; then
        echo "No image file found, skipping upload"
        continue
    fi
    image_path="$image_folder/$image_path"
    echo $image_path
    # Upload the image to AWS S3
    rooms=("RoomA" "RoomB" "RoomC")
    random_room=${rooms[$RANDOM % ${#rooms[@]}]}

    # Upload the image to a random room directory in AWS S3
    aws s3api put-object --bucket $S3_BUCKET --key "${random_room}/image_${timestamp}.jpg" --body "$image_path"
    #aws s3api put-object --bucket $S3_BUCKET --key "image_${timestamp}.jpg" --body "$image_path"

    # Optional: Remove the image after uploading it to S3
    rm "$image_path"

    image_count=$(aws s3 ls s3://$S3_BUCKET/$random_room/ --recursive | wc -l)
    echo "Image count in $random_room: $image_count"
    
    # If there are more than 10 images in the room directory, delete the oldest ones
    if [ "$image_count" -gt 10 ]; then
        # List all files sorted by last modified time (oldest first) and delete the oldest files
	files_to_delete=$(aws s3 ls s3://$S3_BUCKET/$random_room/ --recursive | grep -v 'PRE' | sort | head -n $(($image_count - 10)) | awk '{print $4}' | grep -v '/$')        
#files_to_delete=$(aws s3 ls s3://$S3_BUCKET/$random_room/ --recursive --query "reverse(sort_by(Contents, &LastModified))[:${image_count}-10].Key" --output text)
 	echo ${files_to_delete[@]}       
        # Delete the oldest files
        for file in $files_to_delete; do
            echo "Deleting old file from $random_room: $file"
	    aws s3 rm "s3://$S3_BUCKET/$file"
        done
    fi

    # Sleep for 60 seconds before capturing the next image
    sleep 10
done

