import frappe
import pyfcm
from frappe.model.document import Document
from pyfcm import FCMNotification
import json
import datetime
import requests
import google.auth.transport.requests
from google.oauth2 import service_account

class PushNotification(Document):
    def after_insert(self):
        if self.send_for == "Single User":
            token = frappe.db.get_value(
                "Employee Device Info",
                filters={"user": self.user},
                fieldname="token",
            )
            if token:
                self.response = json.dumps(
                    send_single_notification(
                        token,
                        self.title,
                        self.message,
                        self.user,
                        self.notification_type,
                    )
                )
                self.save()

        elif self.send_for == "Multiple User":
            users = [nu.user for nu in self.users]
            registration_ids = frappe.db.get_list(
                "Employee Device Info",
                filters=[
                    ["Employee Device Info", "user", "in", users],
                    ["Employee Device Info", "token", "is", "set"],
                ],
                fields=["token"],
            )
            if registration_ids:
                registration_ids = [token["token"] for token in registration_ids]
                self.response = json.dumps(
                    send_multiple_notification(
                        registration_ids,
                        self.title,
                        self.message,
                        self.notification_type,
                    )
                )
                self.save()
        elif self.send_for == "All User":
            registration_ids = frappe.db.get_list(
                "Employee Device Info",
                filters=[["Employee Device Info", "token", "is", "set"]],
                fields=["token"],
            )
            if registration_ids:
                registration_ids = [token["token"] for token in registration_ids]
                self.response = json.dumps(
                    send_multiple_notification(
                        registration_ids,
                        self.title,
                        self.message,
                        self.notification_type,
                    )
                )
                self.save()

def _get_access_token():
    settings = frappe.get_single('Employee Self Service Settings')
    file_url = settings.firebase_server_key
    file_path= frappe.get_site_path() + file_url
    SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']
    credentials = service_account.Credentials.from_service_account_file(
        file_path, scopes=SCOPES)
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

@frappe.whitelist()
def send_single_notification(
    registration_id,
    title=None,
    message=None,
    user=None,
    notification_type=None,
):
    PROJECT_ID = 'rfc-ess'
    BASE_URL = 'https://fcm.googleapis.com'
    FCM_ENDPOINT = f'v1/projects/{PROJECT_ID}/messages:send'
    FCM_URL = f'{BASE_URL}/{FCM_ENDPOINT}'
    headers = {
        'Authorization': f'Bearer {_get_access_token()}',
        'Content-Type': 'application/json; UTF-8',
        "Accept": "application/json",
    }
    data = {
            "message": {
                "token": registration_id,
                "notification": {
                    "title": title,
                    "body": message
                },
                "data": {
                    'notification_type': notification_type,
                },
            }
        }
    response = requests.post(FCM_URL, data=json.dumps(data), headers=headers)
    return response.json()

@frappe.whitelist()
def send_multiple_notification(
    registration_ids, title=None, message=None, notification_type=None
):
    responses = []
    for registration_id in registration_ids:
        response = send_single_notification(
            registration_id,
            title,
            message,
            notification_type=notification_type
        )
        responses.append(response)
    return responses

def create_push_notification(title, message, send_for, notification_type, user=None):
    push_notification_doc = frappe.new_doc("Push Notification")
    push_notification_doc.title = title
    push_notification_doc.message = message
    push_notification_doc.send_for = send_for
    push_notification_doc.user = user
    push_notification_doc.notification_type = notification_type
    push_notification_doc.save(ignore_permissions=True)
