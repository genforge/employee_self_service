# Copyright (c) 2024, Nesscale Solutions Private Limited and contributors
# For license information, please see license.txt

import json
import os

import frappe
from frappe import _
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import add_to_date, cast, nowdate, validate_email_address
from frappe.utils.jinja import validate_template
from frappe.utils.safe_exec import get_safe_globals

FORMATS = {"HTML": ".html", "Markdown": ".md", "Plain Text": ".txt"}

class FCMNotification(Document):
	def autoname(self):
		if not self.name:
			self.name = self.subject

	def validate(self):
		validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		self.validate_condition()
		frappe.cache.hdel("notifications", self.document_type)

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, None, get_context(temp_doc.as_dict()))
			except Exception:
				frappe.throw(_("The Condition '{0}' is invalid").format(self.condition))
    
	def get_documents_for_today(self):
		"""get list of documents that will be triggered today"""
		docs = []

		diff_days = self.days_in_advance
		if self.event == "Days After":
			diff_days = -diff_days

		reference_date = add_to_date(nowdate(), days=diff_days)
		reference_date_start = reference_date + " 00:00:00.000000"
		reference_date_end = reference_date + " 23:59:59.000000"

		doc_list = frappe.get_all(
			self.document_type,
			fields="name",
			filters=[
				{self.date_changed: (">=", reference_date_start)},
				{self.date_changed: ("<=", reference_date_end)},
			],
		)

		for d in doc_list:
			doc = frappe.get_doc(self.document_type, d.name)

			if self.condition and not frappe.safe_eval(self.condition, None, get_context(doc)):
				continue

			docs.append(doc)

		return docs


	def on_trash(self):
		frappe.cache.hdel("notifications", self.document_type)


@frappe.whitelist()
def get_documents_for_today(notification):
	notification = frappe.get_doc("ESS Notification", notification)
	notification.check_permission("read")
	return [d.name for d in notification.get_documents_for_today()]


def trigger_daily_alerts():
	trigger_notifications(None, "daily")


def trigger_notifications(doc, method=None):
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send notifications while syncing or patching
		return

	if method == "daily":
		doc_list = frappe.get_all(
			"ESS Notification", filters={"event": ("in", ("Days Before", "Days After")), "enabled": 1}
		)
		for d in doc_list:
			alert = frappe.get_doc("ESS Notification", d.name)

			for doc in alert.get_documents_for_today():
				evaluate_alert(doc, alert, alert.event)
				frappe.db.commit()


def evaluate_alert(doc: Document, alert, event):
	from jinja2 import TemplateError

	try:
		if isinstance(alert, str):
			alert = frappe.get_doc("ESS Notification", alert)

		context = get_context(doc)

		if alert.condition:
			if not frappe.safe_eval(alert.condition, None, context):
				return

		if event == "Value Change" and not doc.is_new():
			if not frappe.db.has_column(doc.doctype, alert.value_changed):
				alert.db_set("enabled", 0)
				alert.log_error(f"Notification {alert.name} has been disabled due to missing field")
				return

			doc_before_save = doc.get_doc_before_save()
			field_value_before_save = doc_before_save.get(alert.value_changed) if doc_before_save else None

			fieldtype = doc.meta.get_field(alert.value_changed).fieldtype
			if cast(fieldtype, doc.get(alert.value_changed)) == cast(fieldtype, field_value_before_save):
				# value not changed
				return

		if event != "Value Change" and not doc.is_new():
			# reload the doc for the latest values & comments,
			# except for validate type event.
			doc.reload()
		alert.send(doc)
	except TemplateError:
		message = _("Error while evaluating Notification {0}. Please fix your template.").format(
			frappe.utils.get_link_to_form("ESS Notification", alert.name)
		)
		frappe.throw(message, title=_("Error in Notification"))
	except Exception as e:
		title = str(e)
		frappe.log_error(title=title)

		msg = f"<details><summary>{title}</summary>{message}</details>"
		frappe.throw(msg, title=_("Error in Notification"))


def get_context(doc):
	return {
		"doc": doc,
		"nowdate": nowdate,
		"frappe": frappe._dict(utils=get_safe_globals().get("frappe").get("utils")),
	}