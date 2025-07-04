from . import __version__ as app_version

app_name = "resource_management"
app_title = "Resource Management"
app_publisher = "Yazan Hamdan"
app_description = "Resource Management and Allocation System"
app_icon = "octicon octicon-organization"
app_color = "blue"
app_email = "your-email@example.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/resource_management/css/resource_management.css"
# app_include_js = "/assets/resource_management/js/resource_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/resource_management/css/resource_management.css"
# web_include_js = "/assets/resource_management/js/resource_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "resource_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "resource_management.utils.jinja_methods",
# 	"filters": "resource_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "resource_management.install.before_install"
# after_install = "resource_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "resource_management.uninstall.before_uninstall"
# after_uninstall = "resource_management.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "resource_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Resource Allocation": "resource_management.api.resource_allocation.get_permission_query_conditions",
}

has_permission = {
	"Resource Allocation": "resource_management.api.resource_allocation.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Resource Allocation": {
		"validate": "resource_management.api.resource_allocation.validate_resource_allocation_status_change",
		"before_save": "resource_management.api.resource_allocation.before_save_resource_allocation",
		"on_submit": "resource_management.api.resource_allocation.on_submit_resource_allocation",
		"on_cancel": "resource_management.api.resource_allocation.on_cancel_resource_allocation"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"resource_management.scheduled_tasks.task_config.daily"
	],
	"weekly": [
		"resource_management.scheduled_tasks.task_config.weekly"
	],
	"monthly": [
		"resource_management.scheduled_tasks.task_config.monthly"
	]
}

# Testing
# -------

# before_tests = "resource_management.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "resource_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "resource_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"resource_management.auth.validate"
# ]
