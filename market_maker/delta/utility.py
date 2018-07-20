import operator
import boto3
from botocore.exceptions import ClientError
from decimal import *


def order_convert_format(price, size, side, product_id):
    order = {
        'product_id': product_id,
        'limit_price': Decimal(price),
        'size': size,
        'side': side,
        'order_type': 'limit_order'
    }
    return order


def round_by_tick_size(price, tick_size, floor_or_ceil=None):
    remainder = price % tick_size
    if remainder == 0:
        return price
    if floor_or_ceil == None:
        floor_or_ceil = 'ceil' if (remainder >= tick_size / 2) else 'floor'
    if floor_or_ceil == 'ceil':
        return price - remainder + tick_size
    else:
        return price - remainder


def takePrice(elem):
    return float(elem['limit_price'])


def takeFirst(elem):
    return elem[0]


def cancel_order_format(x):
    order = {
        'id': x['id'],
        'product_id': x['product']['id']
    }
    return order


def emailer(message, recipient):
    # Replace sender@example.com with your "From" address.
    # This address must be verified with Amazon SES.
    SENDER = "Team Delta <no-reply@delta.exchange>"

    # Replace recipient@example.com with a "To" address. If your account
    # is still in the sandbox, this address must be verified.
    RECIPIENT = "saurabh.goyal@delta.exchange"

    # Specify a configuration set. If you do not want to use a configuration
    # set, comment the following variable, and the
    # ConfigurationSetName=CONFIGURATION_SET argument below.
    # CONFIGURATION_SET = "ConfigSet"

    # If necessary, replace us-west-2 with the AWS Region you're using for Amazon SES.
    AWS_REGION = "us-east-1"

    # The subject line for the email.
    SUBJECT = "Trading Bot has stopped"

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = ("Arbitrage bot has stoped\r\n"
                 "This email was sent to notify that"
                 "the market making bot has terminated its process as %s " % message
                 )

    # The HTML body of the email.
    BODY_HTML = ("""<html>
    <head></head>
    <body>
      <h1>Amazon SES Test (SDK for Python)</h1>
      <p>This email was sent to notify that the market making bot has terminated its process as %s.</p>
    </body>
    </html>
                """ % message)

    # The character encoding for the email.
    CHARSET = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses', region_name=AWS_REGION)

    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
            # If you are not using a configuration set, comment or delete the
            # following line
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
