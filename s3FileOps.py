# !/usr/bin/env python3

import os
import re
import boto3
import configparser
import logging

try:
    os.makedirs("logs")
except:
    pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Use WARNING or above logging when deploying.
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('logs/all.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
# stream_handler.setLevel(logging.ERROR)
# Use WARNING or above logging when deploying.
logger.addHandler(stream_handler)


def fetchConfigs(configFile):
    configData = configparser.ConfigParser()
    configData.read(configFile)
    return configData


def connectionTest(access_id, access_key, region):
    try:
        s3Session = boto3.client('s3', aws_access_key_id=access_id, aws_secret_access_key=access_key,
                                 region_name=region)
        return {"Access Status": True, "Session": s3Session}
    except Exception as e:
        logger.critical("Please check credentials")
        return {"Access Status": False, "Session": e}


def cliParameterFetch():
    import argparse
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--source", help="Input Source Bucket", required=True)
        parser.add_argument("--destination", help="Input Source Bucket", required=True)
        parser.add_argument("--fileName", help="Input Source Bucket", required=True)
        argsData = parser.parse_args()
        src = argsData.source
        dest = argsData.destination
        target = argsData.fileName
        return src, dest, target
    except Exception as e:
        logger.debug(e)
        raise e


def connectToS3Client(aws_access_key_id, aws_secret_access_key):
    try:
        session = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        return session
    except  Exception as e:
        logger.error(e)


def connectToS3Resouce(aws_access_key_id, aws_secret_access_key):
    try:
        session = boto3.resource(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        return session
    except  Exception as e:
        logger.error(e)


def createBucket(bucketID, session_client):
    try:
        logger.debug("Creating bucket")
        session_client.create_bucket(Bucket=bucketID)
        logger.debug(f"Created bucket {bucketID}")
        return True
    except Exception as e:
        logger.error(e)
        return False


def deleteBucket(bucketID, session_resource):
    logger.warning("Deleting bucket")
    try:
        session_resource.Bucket(bucketID).object_versions.delete()
    except Exception as e:
        logger.error(e)
    try:
        session_resource.Bucket(bucketID).objects.all().delete()
    except Exception as e:
        logger.error(e)
    try:
        session_resource.Bucket(bucketID).delete()
    except Exception as e:
        logger.error(e)


def s3ClientInit():
    # fetch configs (access credentials)
    configData = fetchConfigs(configFile='app.config')

    if min(len(configData['AWS Global']['accessID']),len(configData['AWS Global']['accessKey']),len(configData['AWS Global']['regionName'])) == 0:
        raise Exception("Please check credentials")

    # test connection
    s3SessionStatus = connectionTest(access_id=configData['AWS Global']['accessID'],
                                     access_key=configData['AWS Global']['accessKey'],
                                     region=configData['AWS Global']['regionName'])

    # Connect to S3 instance
    session_resource = connectToS3Resouce(aws_access_key_id=configData['AWS Global']['accessKey'],
                                          aws_secret_access_key=configData['AWS Global']['accessID'])

    session_client = connectToS3Client(aws_access_key_id=configData['AWS Global']['accessKey'],
                                       aws_secret_access_key=configData['AWS Global']['accessID'])

    return session_resource, session_client


def filePrepActions(session_client, src, dest, target):
    itemsInBucketLister = lambda x, y: True if y in [re.findall(r"[^/]+", key['Key'])[0] for key in
                                                     session_client.list_objects(Bucket=x)['Contents']] else False
    itemsInBucketListerFullPath = lambda x, y: True if y in [key['Key'] for key in
                                                             session_client.list_objects(Bucket=x)[
                                                                 'Contents']] else False
    filePrep = False
    overwritePermit = True

    # Check if file to move exists in src
    while not filePrep:
        if itemsInBucketListerFullPath(src, target):
            logger.info(f"{target} exists in {src}")
        else:
            logger.warning("Please verify target filename or path, use below listing as reference")
            logger.warning("\n".join([key['Key'] for key in session_client.list_objects(Bucket=src)['Contents']]))
            src = input()

        # Check if file to move exists in dest and overwrite required
        try:
            if itemsInBucketListerFullPath(dest, target):
                logger.debug(f"{target} exists in {dest}. Overwrite? [Y/n]")
                if (input()).upper().rstrip().lstrip() == "N":
                    raise Exception("Overwrite denied. Quitting")
        except Exception as e:
            pass

        return True


if __name__ == '__main__':
    pass


def fileTransfer(session_client, target, src, dest):
    try:
        os.makedirs("cache")
    except:
        pass

    with open("cache/" + target.split("/")[-1], 'wb') as f:
        session_client.download_fileobj(src, target, f)

    try:
        session_client.upload_file("cache/" + target.split("/")[-1], dest, target)
    except Exception as e:
        logger.warning(e)


if __name__ == '__main__':
    '''
    RUNTIME format
    python3 s3FileOps.py --source SOURCE --destination DESTINATION --fileName FILENAME
    '''

    # input CLI
    src, dest, target = cliParameterFetch()

    '''
    # REMOVE AFTER TESTING
    '''
    # [exists]
    # src, dest, target = "aa-parth-test", "new-sooraj-dest", "test/main1.yml"
    # [not exists]
    # src, dest, target = "aa-sooraj-test1", "new-sooraj-dest", "inputFile"

    # S3 Client actions
    session_resource, session_client = s3ClientInit()

    # Call S3 to list current buckets
    listOfBuckets = [bucket.name for bucket in session_resource.buckets.all()]

    bucketPrep = lambda x: True if x in listOfBuckets else False
    bucketPrepNCreate = lambda x: True if x in listOfBuckets else createBucket(x, session_client)

    # Check if src and dest available
    if bucketPrep(src):
        if bucketPrepNCreate(dest):
            filePrep = filePrepActions(session_client, src, dest, target)
            if filePrep:
                fileTransfer(session_client, target, src, dest)
                [os.remove("cache/"+x) for x in os.listdir("cache")]
                os.removedirs("cache")
                logger.warning("Transfer completed")
    else:
        logger.warning(f"Source bucket {src} does not exist")
        exit()
    # TODO (OPTIONAL) delete bucket post operation
    # deleteBucket(src, session_resource)
    # deleteBucket(bucketID=dest, session_resource=session_resource)
