app_name = "resource_management"
app_title = "Resource Management"
app_publisher = "Yazan Hamdan"
app_description = "Resource Management"
app_email = "yazan01mfh@gmail.com"
app_license = "mit"

# Scheduled Tasks
# ---------------

scheduler_events = {
    "all": [
        "resource_management.scheduled_tasks.task_config.all"
    ],
    "daily": [
        "resource_management.scheduled_tasks.task_config.daily"
    ],
    "hourly": [
        "resource_management.scheduled_tasks.task_config.hourly"
    ],
    "weekly": [
        "resource_management.scheduled_tasks.task_config.weekly"
    ],
    "monthly": [
        "resource_management.scheduled_tasks.task_config.monthly"
    ],
}

# Installation
# ------------

before_install = "resource_management.install.before_install"
after_install = "resource_management.install.after_install"
