import json
import base64
import os
from collections.abc import Iterable
from six import string_types
import frappe
from frappe.utils import flt
from frappe import _
from frappe.utils import get_files_path, cint
from frappe.utils.file_manager import save_file
from frappe.utils import nowdate, nowtime, get_first_day, getdate
from frappe.auth import LoginManager

def log_error(title, error):
    frappe.log_error(frappe.get_traceback(), title)

def flatten(lis):
    for item in lis:
        if isinstance(item, Iterable) and not isinstance(item, str):
            for x in flatten(item):
                yield x
        else:        
            yield item

@frappe.whitelist(allow_guest=True)
def create_review(service, customer, stars, review=None):
    try:
        if not service or not customer:
            frappe.response["status"] = False
            frappe.response["message"] = "Service and Customer are required"
            frappe.response["data"] = []
            return

        if stars < 1 or stars > 5:
            frappe.response["status"] = False
            frappe.response["message"] = "Stars must be between 1 and 5"
            frappe.response["data"] = []
            return

        if frappe.db.exists("Reviews", {"service": service, "customer": customer}):
            frappe.response["status"] = False
            frappe.response["message"] = "You already reviewed this service"
            frappe.response["data"] = []
            return

        doc = frappe.get_doc({
            "doctype": "Reviews",
            "service": service,
            "customer": customer,
            "stars": stars,
            "review": review
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Review Created Successfully"
        frappe.response["data"] = {"id": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Review Error")
        frappe.response["status"] = False
        frappe.response["message"] = str(e)
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def update_review(review_id, stars=None, review=None):
    try:
        doc = frappe.get_doc("Reviews", review_id)

        if stars is not None:
            if stars < 1 or stars > 5:
                frappe.response["status"] = False
                frappe.response["message"] = "Stars must be between 1 and 5"
                frappe.response["data"] = []
                return
            doc.stars = stars

        if review is not None:
            doc.review = review

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Review Updated Successfully"
        frappe.response["data"] = {"id": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Review Error")
        frappe.response["status"] = False
        frappe.response["message"] = str(e)
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def delete_review(review_id):
    try:
        frappe.delete_doc("Reviews", review_id, ignore_permissions=True, force=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Review Deleted Successfully"
        frappe.response["data"] = []

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Review Error")
        frappe.response["status"] = False
        frappe.response["message"] = str(e)
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def add_like(review_id, customer):
    try:
        doc = frappe.get_doc("Reviews", review_id)

        for row in doc.disliked_by:
            if row.customer == customer:
                doc.remove(row)
                break

        if not any(row.customer == customer for row in doc.liked_by):
            doc.append("liked_by", {"customer": customer})

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Liked Successfully"
        frappe.response["data"] = {"likes": len(doc.liked_by)}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add Like Error")
        frappe.response["status"] = False
        frappe.response["message"] = str(e)
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def toggle_like(review_id, customer):
    try:
        doc = frappe.get_doc("Reviews", review_id)

        already_liked = False

        for row in doc.liked_by:
            if row.customer == customer:
                doc.remove(row)
                already_liked = True
                break

        if already_liked:
            action = "Like removed"
        else:
            for row in doc.disliked_by:
                if row.customer == customer:
                    doc.remove(row)
                    break

            doc.append("liked_by", {"customer": customer})
            action = "Liked"

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = action
        frappe.response["data"] = {
            "likes_count": len(doc.liked_by),
            "dislikes_count": len(doc.disliked_by)
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Toggle Like Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []

@frappe.whitelist(allow_guest=True)
def toggle_dislike(review_id, customer):
    try:
        doc = frappe.get_doc("Reviews", review_id)

        already_disliked = False

        for row in doc.disliked_by:
            if row.customer == customer:
                doc.remove(row)
                already_disliked = True
                break

        if already_disliked:
            action = "Dislike removed"
        else:
            for row in doc.liked_by:
                if row.customer == customer:
                    doc.remove(row)
                    break

            doc.append("disliked_by", {"customer": customer})
            action = "Disliked"

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = action
        frappe.response["data"] = {
            "likes_count": len(doc.liked_by),
            "dislikes_count": len(doc.disliked_by)
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Toggle Dislike Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = []