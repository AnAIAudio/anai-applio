import os
from typing import Literal
import boto3
from botocore.exceptions import NoCredentialsError


def get_boto3_session(
    client_type: Literal["s3", "secretsmanager", "accessanalyzer"] = "s3",
    region_name: str | None = "ap-northeast-1",
):
    """
    AWS에서 사용할 수 있는 Boto3 세션 가져오기
    Access Key 및 Secret Key는 AWS Cli 설치해서 설정하기.
    """

    boto_session = boto3.client(client_type, region_name=region_name)
    return boto_session


def get_aws_secret(secret_name: str = "dev/rds/anai-dev"):
    import json
    from mypy_boto3_secretsmanager.client import SecretsManagerClient

    try:
        s3_client: SecretsManagerClient = get_boto3_session(
            client_type="secretsmanager"
        )
        get_secret_value_response = s3_client.get_secret_value(SecretId=secret_name)
        return json.loads(get_secret_value_response["SecretString"])
    except Exception as e:
        print(e)
        raise


def download_from_s3(object_name: str, bucket: str = "anaitimbre", file_dir_name=None):
    """
    S3 버킷에서 파일을 다운로드합니다.

    :param object_name: 다운로드할 S3 객체 이름
    :param bucket: 파일이 저장된 S3 버킷 이름
    :param file_dir_name: 로컬에 저장할 파일 이름 (기본값: None, object_name과 동일하게 저장)

    :return: True if file was downloaded, else False
    """
    # file_name이 제공되지 않으면 object_name 사용
    if file_dir_name is None:
        file_dir_name = object_name

    try:
        s3_client = get_boto3_session()
        s3_client.download_file(bucket, object_name, file_dir_name)
        return True
    except FileNotFoundError:
        return False
    except NoCredentialsError:
        return False


def upload_to_s3(file_name: str, bucket: str = "anaitimbre", object_url=None):
    """
    파일을 S3 버킷에 업로드합니다.

    :param file_name: 업로드할 파일의 로컬 경로
    :param bucket: 파일을 업로드할 S3 버킷 이름
    :param object_url: S3 버킷에 저장할 파일 이름 (기본값: None, 파일 이름과 동일하게 저장)
    :return: True if file was uploaded, else False
    """

    if object_url is None:
        object_url = os.path.basename(file_name)
    boto_session = get_boto3_session()
    response = boto_session.upload_file(file_name, bucket, object_url)
    return response


def check_file_exist(file_path: str, bucket: str = "anaitimbre"):
    """
    AWS S3에 파일이 저장되어 있는지 확인
    """
    if not file_path:
        return False

    import botocore

    try:
        boto_session = get_boto3_session()
        boto_session.head_object(Bucket=bucket, Key=file_path)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print(f"Key: '{file_path}' does not exist!")
            import time

            time.sleep(1)
            return False
        else:
            print("Something else went wrong")
            raise


def delete_from_s3(bucket: str = "anaitimbre", object_url: str = None):
    boto_session = get_boto3_session()
    response = boto_session.delete_object(Bucket=bucket, Key=object_url)
    return response


def create_presigned_url(
    bucket_name: str,
    object_url: str,
    expiration: int = 3600,
    attach_file_name: str = "",
):
    """
    presigned URL을 생성합니다.
    :param bucket_name: S3 버킷 이름
    :param object_url: 버킷 내 객체 이름
    :param expiration: presigned URL의 만료 시간(초 단위, 기본 3600초)
    :param attach_file_name: 다운로드 받을 때 지정할 파일 이름
    :return: URL 문자열
    """
    import urllib.parse

    s3_client = get_boto3_session()

    encoded_filename = urllib.parse.quote(attach_file_name)  # -> UTF-8로 URL 인코딩

    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": object_url,
            "ResponseContentDisposition": content_disposition,
        },
        ExpiresIn=expiration,
    )
    return presigned_url
