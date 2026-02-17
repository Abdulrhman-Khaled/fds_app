import json
import base64
import os
from collections.abc import Iterable
from six import string_types
import frappe
from frappe.utils import flt
from frappe import _
from frappe.utils import get_files_path
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
def social_login(**kwargs):
    try:
        if frappe.request.method == "POST":
            data = json.loads(frappe.request.data)
        else:
            data = kwargs

        login_type = data.get("login_type")
        email = data.get("email")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        profile_image = data.get("profile_image")

        if not email:
            frappe.response.update({
                "status": False,
                "message": "Email is required",
                "data": {}
            })
            return


        user_name = frappe.db.get_value("User", {"email": email}, "name")

        if user_name:
            user = frappe.get_doc("User", user_name)


            if not user.bio:
                user.bio = login_type

            if profile_image and user.user_image != profile_image:
                user.user_image = profile_image

            user.save(ignore_permissions=True)

            frappe.response.update({
                "status": True,
                "message": "login success",
                "data": _user_to_dict(user)
            })
            return


        full_name = f"{first_name or ''} {last_name or ''}".strip()

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "enabled": 1,
            "bio": login_type,
            "user_type": "Website User",
            "user_image": profile_image or "",
            "send_welcome_email": 0
        })
        user.insert(ignore_permissions=True)

        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": full_name,
            "customer_type": "Individual",
            "email_id": email
        })
        customer.insert(ignore_permissions=True)

        customer.custom_user = user.name
        customer.save(ignore_permissions=True)

        frappe.response.update({
            "status": True,
            "message": "user created",
            "data": _user_to_dict(user)
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Social Login Error")
        frappe.response.update({
            "status": False,
            "message": f"Server Error: {str(e)}",
            "data": {}
        })

def _user_to_dict(user):
    return {
        "id": user.name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "login_type": user.bio,
        "full_name": user.full_name,
        "profile_image": frappe.utils.get_url(user.user_image) if user.user_image else "",
        "created_at": str(user.creation),
        "updated_at": str(user.modified),
    }

@frappe.whitelist(allow_guest=True)
def register(**kwargs):
    try:
        if frappe.request and frappe.request.method == "POST":
            data = json.loads(frappe.request.data)
        else:
            data = kwargs

        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        password = data.get("password")
        gender = data.get("gender", "").lower()
        user_type = data.get("user_type", "email")

        if not first_name or not email or not password:
            frappe.response["status"] = False
            frappe.response["message"] = "First name, email, and password are required"
            frappe.response["data"] = {}
            return

        if frappe.db.exists("User", {"email": email}):
            frappe.response["status"] = False
            frappe.response["message"] = "Email already registered"
            frappe.response["data"] = {}
            return

        full_name = f"{first_name or ''} {last_name or ''}".strip()

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "user_type": "Website User",
            "enabled": 1,
            "gender": gender,
            "bio": user_type,
            "send_welcome_email": 0
        })
        user.insert(ignore_permissions=True)

        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": full_name,
            "customer_type": "Individual",
            "email_id": email
        })
        customer.insert(ignore_permissions=True)

        user.new_password = password
        user.save(ignore_permissions=True)

        customer.custom_user = user.name
        customer.save(ignore_permissions=True)

        frappe.db.commit()

        frappe.response["status"] = True
        frappe.response["message"] = "Register successful"
        frappe.response["data"] = _register_user_to_dict(user)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Register API Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = {}

def _register_user_to_dict(user):
    customer = frappe.get_doc("Customer", {"custom_user": user})
    return {
        "id": user.name,
        "customer_id": customer.name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "gender": user.gender,
        "login_type": user.bio or "",
    }

@frappe.whitelist(allow_guest=True)
def login(**kwargs):
    try:
        if frappe.request and frappe.request.method == "POST":
            data = json.loads(frappe.request.data)
        else:
            data = kwargs

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            frappe.response["status"] = False
            frappe.response["message"] = "Email and password are required"
            frappe.response["data"] = {}
            return

        if not frappe.db.exists("User", {"email": email}):
            frappe.response["status"] = False
            frappe.response["message"] = "Please register before login"
            frappe.response["data"] = {}
            return

        user = frappe.get_doc("User", {"email": email})

        if not user.enabled:
            frappe.response["status"] = False
            frappe.response["message"] = "Your account is disabled. Contact support."
            frappe.response["data"] = {}
            return

        login_manager = LoginManager()
        login_manager.authenticate(user=email, pwd=password)
        login_manager.post_login()

        logged_user = frappe.get_doc("User", frappe.session.user)

        frappe.response["status"] = True
        frappe.response["message"] = "Login successful"
        frappe.response["data"] = _login_user_to_dict(logged_user)

    except frappe.AuthenticationError:
        frappe.response["status"] = False
        frappe.response["message"] = "Invalid email or password"
        frappe.response["data"] = {}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Login API Error")
        frappe.response["status"] = False
        frappe.response["message"] = f"Server Error: {str(e)}"
        frappe.response["data"] = {}

def _login_user_to_dict(user):
    profile_image = ""
    if user.user_image:
        profile_image = frappe.utils.get_url(user.user_image)

    customer = frappe.get_doc("Customer", {"custom_user": user})

    return {
        "id": user.email,
        "customer_id": customer.name or "",
        "first_name": user.first_name,
        "last_name": user.last_name,
        "mobile": user.mobile_no or "",
        "email": user.email,
        "gender": user.gender or "",
        "user_role": [],
        "api_token": "", 
        "profile_image": profile_image,
        "login_type": user.bio or "",
    }

@frappe.whitelist(allow_guest=True)
def forgot_password(**kwargs):
    try:
        if frappe.request and frappe.request.method == "POST":
            data = json.loads(frappe.request.data)
        else:
            data = kwargs

        email = data.get("email")
        if not email:
            frappe.response.update({
                "status": False,
                "message": "Email is required",
                "data": {}
            })
            return

        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            frappe.response.update({
                "status": False,
                "message": "No account found with this email",
                "data": {}
            })
            return

        user = frappe.get_doc("User", user_name)
        user.validate_reset_password()
        user.reset_password(send_email=True)

        frappe.response.update({
            "status": True,
            "message": "Password reset email sent successfully",
            "data": {}
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Forgot Password API Error")
        frappe.response.update({
            "status": False,
            "message": f"Server Error: {str(e)}",
            "data": {}
        })

@frappe.whitelist(allow_guest=True, methods=["GET"])
def user_detail(id=None):
    try:
        user_id = id or frappe.form_dict.get("id")
        if not user_id:
            frappe.response.update({
                "status": False,
                "message": "User ID is required",
                "data": {}
            })
            return

        user = frappe.get_doc("User", user_id) if frappe.db.exists("User", user_id) \
            else frappe.get_doc("User", {"email": user_id})

        user_data = _user_detail_to_dict(user)

        frappe.response.update({
            "status": True,
            "message": "User details retrieved successfully",
            "data": user_data
        })

    except frappe.DoesNotExistError:
        frappe.response.update({
            "status": False,
            "message": "User not found",
            "data": {}
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "User Detail API Error")
        frappe.response.update({
            "status": False,
            "message": f"Server Error: {str(e)}",
            "data": {}
        })

def _user_detail_to_dict(user):
    file_url = frappe.db.get_value(
        "File",
        {"attached_to_doctype": "User", "attached_to_name": user.name},
        "file_url"
    )

    customer = frappe.get_doc("Customer", {"custom_user": user})

    return {
        "id": user.name,
        "customer_id": customer.name or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "username": getattr(user, "username", "") or "",
        "email": user.email or "",
        "mobile": getattr(user, "mobile_no", "") or "",
        "gender": getattr(user, "gender", "") or "",
        "phone_verified": getattr(user, "phone_verified", 0),
        "login_type": getattr(user, "bio", ""),
        "profile_image": user.user_image or frappe.utils.get_url(file_url) or "",
        "api_token": "",
    }

@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_profile(**kwargs):
    try:
        if frappe.request and frappe.request.method == "POST":
            data = frappe.form_dict or json.loads(frappe.request.data or "{}")
        else:
            data = kwargs

        user_id = data.get("id") or frappe.session.user
        if not user_id:
            frappe.response.update({
                "status": False,
                "message": "User ID is required",
                "data": {}
            })
            return

        if frappe.db.exists("User", user_id):
            user = frappe.get_doc("User", user_id)
        else:
            frappe.response.update({
                "status": False,
                "message": "User not found",
                "data": {}
            })
            return

        if "first_name" in data:
            user.first_name = data.get("first_name")
        if "last_name" in data:
            user.last_name = data.get("last_name")
        if "mobile" in data:
            user.mobile_no = data.get("mobile")
        if "gender" in data:
            user.gender = data.get("gender")
        if "username" in data:
            user.username = data.get("username")

        user.full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        user.save(ignore_permissions=True)

        customer = frappe.get_doc("Customer", {"custom_user": user})
        if "first_name" in data and "last_name" in data:
            customer.customer_name = data.get("first_name") + " " + data.get("last_name")
            customer.save(ignore_permissions=True)



        user_data = _user_to_dict(user)
        frappe.response.update({
            "status": True,
            "message": "Profile updated successfully",
            "data": user_data
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Profile Error")
        frappe.response.update({
            "status": False,
            "message": f"Server Error: {str(e)}",
            "data": {}
        })

def _user_to_dict(user):
    customer = frappe.get_doc("Customer", {"custom_user": user})
    return {
        "id": user.name,
        "customer_id": customer.name or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "email": user.email or "",
        "username": user.username or "",
        "mobile": getattr(user, "mobile_no", "") or "",
        "gender": getattr(user, "gender", "") or "",
        "loginType": getattr(user, "bio", ""),
        "profileImage": user.user_image or "",
    }