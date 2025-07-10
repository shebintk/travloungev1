import os

from datetime import datetime
from io import BytesIO
import boto3
import mimetypes
from botocore.exceptions import ClientError
from django.http import QueryDict
from requests import request
from billing.serializers import DocumentSerializer
import shutil
from django.conf import settings

def upload_image_to_s3(image_file, user_id):
    try:
        # Create an S3 client
        s3_client = boto3.client('s3', 
                                aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
                                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                                )
        # Construct file key
        file_key = f"image/{user_id}_{image_file.name}"
        # Set content type based on filename extension
        content_type = mimetypes.guess_type(file_key)[0] or 'image/jpeg'
        # Upload image to S3
        s3_client.put_object(Body=image_file.read(), 
                             Bucket=settings.AWS_STORAGE_BUCKET_NAME, 
                             Key=file_key, 
                             ContentType=content_type
                             )
        # Return the S3 URL
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
    except ClientError as e:
        # Handle exception or log error
        raise e
    

def upload_to_s3(image, user_id):
    try:
        print("image    = = =", image)
        s3 = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        idProof_content = image.read()
        doc_key = f'idproof/{image.name}'

        s3.upload_fileobj(BytesIO(idProof_content), bucket_name, doc_key)

        id_filename = image.name.replace(" ", "")
        data_to_save = {
            'user': user_id,
            'id_proof': image
        }

        docserializer = DocumentSerializer(data=data_to_save)
        if docserializer.is_valid():
            print("Document saved successfully.")
            docserializer.save()
        else:
            print("Serializer is not valid:", docserializer.errors)
            return {"error": docserializer.errors}

        return {"message": "success"}

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {"error": str(e)}

    finally:
        if os.path.exists("idproof/"):
            shutil.rmtree("idproof/")


def s3_upload(image, file_name_prefix=None, file_folder=None):
    """
    Parameters:
        image (InMemoryUploadedFile): 
            The file object to be uploaded. Typically obtained from a file input field in a Django form or request.
        
        file_name_prefix (str, optional): 
            A prefix to prepend to the file name (Ideally the associated object ID).
            Example: "user123" -> "user123_filename.jpg".
        
        file_folder (str, optional): 
            The folder within the S3 bucket where the file will be stored. 
            Specify the model name.(In singular form).
            Example: "listing_images" -> "listing_images/filename.jpg".
    """

    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        content_type = image.content_type
        image_name,ftype = image.name.rsplit('.', 1)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        s3_key = f'{file_folder}/{str(file_name_prefix) + "_" if file_name_prefix else ""}{image_name.replace(" ", "")[:25] + "_"}{timestamp}{"." + ftype}'

        # Upload image to S3
        s3.upload_fileobj(image, bucket_name, s3_key,ExtraArgs={"ContentType": content_type, "ContentDisposition": "inline"})

        s3_url = f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'

        return {"message": "success", "s3_url": s3_url}

    except Exception as e:
        return {"error": str(e)}