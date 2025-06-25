# حل مؤقت - أضف هذا في بداية ملف resource_allocation.py API

import frappe
from frappe.utils import date_diff, flt
from frappe import _

@frappe.whitelist()
def get_permission_query_conditions(user):
    """
    نسخة مبسطة من permission query conditions
    """
    try:
        if not user:
            user = frappe.session.user or "Guest"
        
        # تحقق من الأدوار بطريقة آمنة
        user_roles = frappe.get_roles(user) if user != "Guest" else []
        
        # System Manager يرى كل شيء
        if "System Manager" in user_roles:
            return ""
        
        # CGO يرى كل شيء
        if "CGO" in user_roles:
            return ""
        
        # الموظفين العاديين يرون طلباتهم فقط
        return f"(`tabResource Allocation`.`requested_by` = '{frappe.db.escape(user)}')"
        
    except Exception as e:
        # في حالة حدوث خطأ، اسمح بالوصول للجميع مؤقتاً
        frappe.log_error(f"Permission Query Error: {str(e)}", "Resource Allocation Permissions")
        return ""

@frappe.whitelist()
def has_permission(doc, user=None, permission_type=None):
    """
    نسخة مبسطة من has_permission
    """
    try:
        if not user:
            user = frappe.session.user or "Guest"
        
        if user == "Guest":
            return False
        
        # تحقق من الأدوار بطريقة آمنة
        user_roles = frappe.get_roles(user)
        
        # System Manager له كل الصلاحيات
        if "System Manager" in user_roles:
            return True
        
        # للمستندات الجديدة، اسمح للجميع بالإنشاء
        if not doc or not hasattr(doc, 'name') or not doc.name:
            return True
        
        # صلاحيات أساسية - الجميع يمكنه القراءة
        if permission_type == 'read':
            return True
        
        # CGO له صلاحيات الموافقة/الرفض
        if "CGO" in user_roles:
            return True
        
        # مالك المستند له صلاحية التعديل إذا كان في حالة Draft
        doc_status = getattr(doc, 'status', 'Draft')
        requested_by = getattr(doc, 'requested_by', None)
        
        if requested_by == user and doc_status == 'Draft':
            return permission_type in ['read', 'write', 'delete']
        
        # باقي الحالات - قراءة فقط
        return permission_type == 'read'
        
    except Exception as e:
        # في حالة حدوث خطأ، اسمح بالوصول مؤقتاً
        frappe.log_error(f"Has Permission Error: {str(e)}", "Resource Allocation Permissions")
        return True
