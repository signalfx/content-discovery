import argparse
import boto3
import logging
import random
import string
import time

from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(filename="cognito.log",
                    format='%(asctime)s %(levelname)s %(message)s',
                    filemode='a')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class CronScript:
    """
    Class is used to have methods related to AWS Cognito.
    """

    def __init__(self):
        # AWS Cognito configuration
        self.region_name = "us-west-1"
        self.user_pool_id = "us-west-1_fgroAQl1f"
        self.user_pool_name = "bits-userpool16"
        self.client_id = "6saq2dnflgg5vn9lv9a7dl0khh"
        self.cognito = boto3.client("cognito-idp")
        self.signup_success_list = []

    # Create User pool
    def create_user_pool(self, args):
        if args.user_pool_name is None:
            logger.info("Argument not passed")
        else:
            user_pool_name = args.user_pool_name
            client = boto3.client("cognito-idp")
            response = client.create_user_pool(
                PoolName=user_pool_name,
                Policies={
                    "PasswordPolicy": {
                        "MinimumLength": 8,
                        "RequireLowercase": True,
                        "RequireUppercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": True,
                    }
                },
                AdminCreateUserConfig={
                    "AllowAdminCreateUserOnly": False,
                    "UnusedAccountValidityDays": 7,
                },
            )

            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                logger.info("User pool created successfully")
                global user_pool_id
                user_pool_id = response["UserPool"]["Id"]
                response_for_client = client.create_user_pool_client(
                    UserPoolId=user_pool_id, ClientName="bits-test-client"
                )
                if response_for_client["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    global client_id
                    client_id = response_for_client["UserPoolClient"]["ClientId"]
                    logger.info(
                        f"User pool client created successfully with ID: {client_id}")

                else:
                    logger.error(
                        "Error creating user pool client: ",
                        response_for_client["Error"]["Message"],
                    )

                response_client_update = client.update_user_pool_client(
                    UserPoolId=user_pool_id,
                    ClientId=client_id,
                    ExplicitAuthFlows=["USER_PASSWORD_AUTH"],
                )
                if response_client_update["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    logger.info(f"CLient updated Successfully {client_id}")
                else:
                    logger.error(
                        f"Error updating the client {client_id}: {response_client_update}"
                    )

            else:
                logger.error("Error creating user pool: ",
                             response["Error"]["Message"])
                exit(0)

    # Generate a random username  for each request
    def random_string(length):
        letters = string.ascii_letters
        return "".join(random.choice(letters) for _ in range(length))

    # create user/user signup
    def admin_create_user(self, **kwargs):
        username = kwargs["username"]
        password = "F&qj1V#Rg4)A"
        email = kwargs["email"]
        cognito = boto3.client("cognito-idp")
        try:
            _ = cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=username,
                TemporaryPassword=password,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                ],
                DesiredDeliveryMediums=[],
                MessageAction="SUPPRESS",
            )
            self.signup_success_list.append(username)
            return username

        except Exception as e:
            logger.error(f"Sign-up failed for {username}: {str(e)}")

    # change passwords
    def change_pass(self):
        cognito = boto3.client("cognito-idp")
        username_for_password_change = self.signup_success_list
        # Loop through the list of usernames and force a change of password
        for username in username_for_password_change:
            response = cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=username,
                Password="New@12345",
                Permanent=True,
            )
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                logger.info(f"Password changed successfully for {username}")
            else:
                logger.error(
                    f"Error changing password for {username}: {response}")

        logger.info("Password change completed")

    # sign-in for users
    def sign_in_user(self, **kwargs):
        # count = kwargs["count"]
        username = kwargs["username"]
        cognito = boto3.client("cognito-idp")
        # Initiate authentication with the user name and password
        try:
            response = cognito.initiate_auth(
                ClientId=client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": "New@12345"},
            )
            if "AuthenticationResult" in response:
                logger.info(f"User {username} signed in with access token")
            else:
                logger.error(f"Error signing in user {username}")

        except Exception as e:
            logger.error(f"Sign-in failed for {username}: {str(e)}")

    # delete new created user pool after 5 mins
    def delete_user_pool(self, args):
        if args.user_pool_name is None:
            logger.info("Argument not passed, user pool will not be deleted")

        else:
            # delete user pool
            logger.info("Waiting for 4 minutes...")
            time.sleep(250)
            logger.info("Done waiting!")
            cognito = boto3.client("cognito-idp")
            delete_response = cognito.delete_user_pool(UserPoolId=user_pool_id)

            if delete_response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                logger.info("User pool deleted successfully")
            else:
                logger.error("Error deleting user pool: ",
                             delete_response["Error"]["Message"])

    # delete users from default user pool
    def delete_users(self, signup_success_list):
        # delete user pool
        logger.info("Waiting for 4 minutes...")
        time.sleep(250)
        logger.info("Done waiting!")
        logger.info(f"Following users will be deleted:{signup_success_list}")
        cognito = boto3.client("cognito-idp")
        try:
            for username in signup_success_list:
                cognito.admin_delete_user(
                    UserPoolId=user_pool_id, Username=username
                )
        except Exception as e:
            logger.error(f"Failed to delete user:{username}: {str(e)}")

    def refresh_cognito_token(self):
        # Define the parameters for the InitiateAuth request
        params = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "AuthParameters": {
                "REFRESH_TOKEN": "eyJjdHkiOiJKV1QiLCJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiUlNBLU9BRVAifQ.WPM3bwnMaE9Jd1OGxQ3Zgez5E8sGcE-Vz98uvTUjR4CODFJux79EwtJpMcQJlnowSNZRTXdzwinn9s0W3sxG5CKIokkcGocCFz0mrD-EZJWGcnvD4NXBfatlZrow5uOuZR9YEQvf3gItZx9pZNROtXDwQ5l_jrLxj-a9e4YEDPzuEWnIhPxQYWJa55_R86KOa-wPl0mY8AgQC-1UfkifgyoQXBZ3RvCp2uwwCrol7zKuNt4vrcgjV1d1wXB5dVZCiwgBMFeMrXqZIl4FWIbMeqZZ3zQHu_19bMXwvwH0vUwP7SapRj-WNqupS-aTDdtyJ2Iii945g4nf7Jm9Rrmv4w.XHLbFyE74_ZTVx1n.A5jzyH6BwkcQCoQpme_MuM89KphnPcQQX6loYoL6izAuq-TIstkb2uddEPXC4_9XQSpQISFwaqKERsCBfWHtS7Yn1qlv0sIDXkqnwvbuuzgc7cc2kw9vRDb0zHLOhF--iiJMfULPk-H-IOeLgicCt6OIaPnHgk8z6w9iPhuAy5j7JMiQU0eEleLMUoFYq4qd0nbbt2_vqSYISHlHJV2CqY3I_Ky38_8ePcmgiiucDfQ7IxK6aenF0JEvY7pBK32lsNeMLvrmY1UAHc7u9fBYvMhwDSKbDp73U--Cs7FG_SJ4b9nhixKN0YZsO6mnILA8jNOoLxlT5WDyzsLhrl_swluJWOPikHgdJSWuG5a4HSQ6MSnM6C_0A0xCV9ItoHslNZrwBovj4H-l1J9Xxvq8d8R-TfSPQ5ob1tTP_-Wtn-YYzj9CZ37QQt9Ho7CqVvfRqzkij6iQub1QSep5HAbOZc1_brG5SQR9Qs9nJKA-j7UtKN3AyloQaaBnQK0bOd3JiigrbGx9HSWOtqsI-Zzl_RFBmVk8wM-kmBh2qHxsg3lGhv2vJ86-A16pB3bo_kwr2JvfjcBMk8KIcujyqZiScpwNeQ6JgnqYoX3o_oPHa2-x5z932WC9MEsjKUDpga_MkwF2qvnqVp8W11QcHZzKFRZyWh6ITpGFLHS7rv5qY1s8vSmwa-XPeO0CBhQxsrmrrQi_ova4dkcXAjNx97es8S-1QH4pvrh2qhPHU4DtySaJnDxjVuVHTlVGsx9DNoJ7c4KugbJUSWcRU5Zz5WQk3PPY9_1pkCpMHHJLgfMQ8Be-NeFVTo-hCRw64DD9gvZx5kFeowsyzVgMu_Fm8Mc3B_44S_ZIF8Y5CpvT78LQtxm4JVnbBN5Lk71RHjZEja4OsbCCRyFnf9cfYaVgPYYETSzt6asVK8eRrBf6wV4ELmYZSjP7WwdmF7_vhEEqrSKNLaLZxmfocBuv6LcKM8zL52SFl8XK1OnKIcf4y0elKgkhDNSNeucEmDKfwIR1_49n6HTURM7P-NCSX4oQ0PDdETwkRWQ3Xg_SawzlKw43fN0-GL4R6MJYXE6BHBCkx6TddaXXmUFQK4MRBpzHPHmNnn4iZhy4blvWlkL6PtTKOlI7P5UMPHZZ3sthAMJzUivFbkuJb5rNiFZ20X5-nqLU6yNQboor6phVFkJeMSIZjQlPyFBaAbFj7ib7exBZfBfyuff1_CS6SvVdbi_8lJYxdznkqWI_LnmJxfzcFwjvPmWlsnlGn135PrMGXJ2CzE9-jTI.Zc0WSyK9pWmSG0rXYses1Q"
            },
            "ClientId": "6saq2dnflgg5vn9lv9a7dl0khh",
        }

        # Execute the InitiateAuth request
        response = self.cognito.initiate_auth(**params)

        # Extract the new access token and ID token from the response
        logger.info("Token Refreshed..")

    # Create multiple threads to simulate concurrent requests
    # for sign up throttle
    # max worker = 500
    # req = 400

    # for sign in throttle
    # max worker = 100
    # req = 1200
    # python3 CronScript.py --totalReq=400 --user-pool-name=bits-userpool25

    def create_threads(self, method):
        with ThreadPoolExecutor(max_workers=500) as executor:
            futures = []
            name = method.__name__
            if name == "sign_in_user":
                logger.info(f"here in {name}")
                for username in self.signup_success_list:
                    futures.append(executor.submit(method, username=username))

            if name == "admin_create_user":
                logger.info(f"here in {name}")
                for i in range(1, num_requests + 1):
                    username = f"bits{i}"
                    email = f"user{i}@example.com"
                    futures.append(
                        executor.submit(
                            method, username=username, email=email, count=i)
                    )

            if name == "refresh_cognito_token":
                logger.info(f"here in {name}")
                for i in range(1, num_requests + 1):
                    futures.append(executor.submit(method, count=i))

            # Wait for all threads to finish
            # for future in as_completed(futures):
            #     name = method.__name__
            #     print(f"here in fff{name}")
            #     if name == "create_admin_user":
            #         self.signup_success_list.append(future.result())
            #         print(self.signup_success_list)
            #         print("User Bulk SignUp completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-pool-name", required=False)
    parser.add_argument("--totalReq", required=False, default=10)
    args = parser.parse_args()

    croneScriptInstance = CronScript()

    # Create userpool
    croneScriptInstance.create_user_pool(args)

    # Number of sign-up requests to simulate
    num_requests = int(args.totalReq)

    # Refresh the cognito token
    croneScriptInstance.create_threads(
        croneScriptInstance.refresh_cognito_token)

    # User sign up
    croneScriptInstance.create_threads(croneScriptInstance.admin_create_user)

    # Change password for each user
    croneScriptInstance.change_pass()

    # User sign in
    croneScriptInstance.create_threads(croneScriptInstance.sign_in_user)

    if args.user_pool_name is None:
        croneScriptInstance.delete_users(
            croneScriptInstance.signup_success_list)
    else:
        croneScriptInstance.delete_user_pool(args)