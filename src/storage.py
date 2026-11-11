import os
from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def _s3_client():
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION"))


def fetch_resume_bytes(s3_key: str) -> bytes:
    obj = _s3_client().get_object(Bucket=os.environ.get("AWS_BUCKET_NAME"), Key=s3_key)
    return obj["Body"].read()
