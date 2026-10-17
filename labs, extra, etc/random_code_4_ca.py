import boto3
import uuid # imported so i don't have to manually add in a bucket name every time...

user_data = """#!/bin/bash
            yum update -y
            yum install httpd -y
            systemctl enable httpd
            systemctl start httpd"""

ec2 = boto3.resource('ec2')
new_instances = ec2.create_instances(
            ImageId='ami-0fef201115eefe936',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.nano',
            Placement={'AvailabilityZone': 'us-east-1b'},
            KeyName='awskey',
            # takes the user data from above
            UserData=user_data,
            # security group id inputted for existing secutiry group, maybe change to making a security group & checking if one already exists
            SecurityGroupIds=['sg-0fc7eca295775e4d3'],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'Web Server CI'
                        }]
                }
            ])

# set the new instance under 'instance' , prints the id , waits until its running & reload , prints that it's running
instance = new_instances[0]
print(instance.id)
instance.wait_until_running()
instance.reload()
print('Instance Running...')

# --- BUCKETS
    # bucket name formatted "'6randomchar'-mroche"
bucket_name = f'{uuid.uuid4().hex[:6]}-mroche'
s3 = boto3.resource('s3')

try:
	s3.create_bucket(Bucket=bucket_name)
except Exception as error:
	print('Could not create bucket: ', error)
	
website_configuration = {
    'ErrorDocument': {'Key': 'error.html'},
    'IndexDocument': {'Suffix': 'index.html'},
}

bucket_website = s3.BucketWebsite(bucket_name)
bucket_website.put(WebsiteConfiguration=website_configuration)

print('Bucket created: ', bucket_name)
print('Upload an index.html file to test it works!')
