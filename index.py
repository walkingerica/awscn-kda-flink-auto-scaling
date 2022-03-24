'''
Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

'''
WARNING: This is a work in progress (and currently, is an incomplete and
         non-functional implementation)
'''

import boto3
import json
import os

client_kda = boto3.client('kinesisanalyticsv2')
client_ssm = boto3.client('ssm')
client_cloudwatch = boto3.client('cloudwatch')
client_cloudformation = boto3.client('cloudformation')
client_aas = boto3.client('application-autoscaling')
client_iam = boto3.resource('iam')

PARAMETER_STORE = os.environ['ParameterStore']


def update_parallelism(context, desiredCapacity, resourceName, appVersionId):
    # Update parallelism to the new Desired Capacity value
    try:
        response = client_kda.update_application(
            ApplicationName=resourceName,
            CurrentApplicationVersionId=appVersionId,
            ApplicationConfigurationUpdate={
                'FlinkApplicationConfigurationUpdate': {
                    'ParallelismConfigurationUpdate': {
                        'ConfigurationTypeUpdate': 'CUSTOM',
                        'ParallelismUpdate': int(desiredCapacity),
                        'AutoScalingEnabledUpdate': False
                    }
                }
            }
        )

        print("In update_parallelism; response: ")
        print(response)
        scalingStatus = "InProgress"

    # In case of error of updating the sharding, raise an exception.
    except Exception as e:
        print(e)
        failureReason = str(e)
        scalingStatus = "Failed"
        pass

    return scalingStatus

def response_function(status_code, response_body):
    return_json = {
        'statusCode': status_code,
        'body': json.dumps(response_body) if response_body else json.dumps({}),
        'headers': {
            'Content-Type': 'application/json',
        },
    }
    # log response
    print(return_json)
    return return_json


def lambda_handler(event, context):
    # log the event
    print("Calling lambda scaler for kda - " + json.dumps(event))

    # get KDA app name
    if 'scalableTargetDimensionId' in event['pathParameters']:
        resourceName = event['pathParameters']['scalableTargetDimensionId']
        print("Fetching resource name in kda scaler - " + resourceName)
    else:
        message = "Error, scalableTargetDimensionId not found"
        return response_function(400, str(message))

    # get details for the KDA app in question
    try:
        response = client_kda.describe_application(
            ApplicationName=resourceName
        )

        print("In kda scaler, response from kda.describe_application")
        print(response)

        appVersion = response["ApplicationDetail"]["ApplicationVersionId"]
        applicationStatus = response["ApplicationDetail"]["ApplicationStatus"]
        parallelism = response["ApplicationDetail"]["ApplicationConfigurationDescription"][
            "FlinkApplicationConfigurationDescription"]["ParallelismConfigurationDescription"]["Parallelism"]
        actualCapacity = parallelism
    except Exception as e:
        print("Exception in kda scaler: " + str(e))
        message = "Error, cannot find a kinesis data analytics app called " + resourceName
        return response_function(404, message)

    # try to retrive the desired capacity from ParameterStore

    response = client_ssm.get_parameter(
        Name=PARAMETER_STORE
    )
    print("In kda scaler, just called ssm.get_parameter (1)")
    print(response)


    if 'Parameter' in response:
        if 'Value' in response['Parameter']:
            desiredCapacity = response['Parameter']['Value']
            print("In kda scaler, desiredCapacity: " + str(desiredCapacity))
    else:
        # if I do not have an entry in ParameterStore, I assume that the desiredCapacity = actualCapacity
        desiredCapacity = actualCapacity

    if applicationStatus == "UPDATING":
        scalingStatus = "InProgress"
    elif applicationStatus == "RUNNING":
        scalingStatus = "Successful"

    print("In kda scaler, scalingStatus: " + scalingStatus)

    if event['httpMethod'] == "PATCH":

        # Check whether autoscaling is calling to change the Desired Capacity
        if 'desiredCapacity' in event['body']:
            desiredCapacityBody = json.loads(event['body'])
            desiredCapacityBody = desiredCapacityBody['desiredCapacity']

            # Check whether the new desired capacity is negative. If so, I need to calculate the new desired capacity
            if int(desiredCapacityBody) >= 0:
                desiredCapacity = desiredCapacityBody

                # Store the new desired capacity in a ParameterStore
                response = client_ssm.put_parameter(
                    Name=PARAMETER_STORE,
                    Value=str(int(desiredCapacity)),
                    Type='String',
                    Overwrite=True
                )
                print(response)
                print("In kda scaler, trying to set capacity to " + str(desiredCapacity))

                if scalingStatus == "Successful" and int(desiredCapacity) != int(actualCapacity):
                    scalingStatus = update_parallelism(context, desiredCapacity, resourceName, appVersion)
            else:
                print("desiredCapacity was < 0")

    elif event['httpMethod'] == "GET":
        if scalingStatus == "Successful" and int(desiredCapacity) != int(actualCapacity):
            scalingStatus = update_parallelism(context, desiredCapacity, resourceName, appVersion)
        elif scalingStatus == "Successful":
            print("Scaling successful; not doing anything")

    else:
        print("Unknown http method!: " + event['httpMethod'])

    # Do NOT change the version in response!
    # Doing so will cause the scalable target
    # to get unregistered along with the attached
    # scaling policies.
    returningJson = {
        "actualCapacity": float(actualCapacity),
        "desiredCapacity": float(desiredCapacity),
        "dimensionName": resourceName,
        "resourceName": resourceName,
        "scalableTargetDimensionId": resourceName,
        "scalingStatus": scalingStatus,
        "version": "KDAScaling"
    }

    try:
        returningJson['failureReason'] = failureReason
    except:
        pass

    print(returningJson)

    return response_function(200, returningJson)
