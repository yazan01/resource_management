// Copyright (c) 2023, Yazan Hamdan and contributors
// For license information, please see license.txt

frappe.listview_settings['Resource Allocation'] = {
	add_fields: ["status", "start_date", "end_date", "employee_name", "project_name"],
	
	get_indicator: function(doc) {
		if (doc.status === "Requested") {
			return [__("Requested"), "orange", "status,=,Requested"];
		} else if (doc.status === "Approved") {
			// Check if allocation is current, future, or past
			var today = frappe.datetime.get_today();
			
			if (doc.start_date > today) {
				return [__("Upcoming"), "blue", "status,=,Approved"];
			} else if (doc.end_date < today) {
				return [__("Completed"), "green", "status,=,Approved"];
			} else {
				return [__("Active"), "green", "status,=,Approved"];
			}
		} else if (doc.status === "Rejected") {
			return [__("Rejected"), "red", "status,=,Rejected"];
		} else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		}
		
		return [__(doc.status), "gray", "status,=," + doc.status];
	},
	
	// Add button to request new allocation
	onload: function(listview) {
		listview.page.add_action_item(__('Request New Allocation'), function() {
			frappe.new_doc('Resource Allocation');
		});
	},
	
	// Add bulk actions for approving/rejecting allocations
	button: {
		show: function(doc) {
			return doc.status === "Requested";
		},
		get_label: function() {
			return __('Approve');
		},
		get_description: function(doc) {
			return __('Approve {0}', [doc.employee_name]);
		},
		action: function(doc) {
			frappe.confirm(
				__('Are you sure you want to approve this resource allocation?'),
				function() {
					frappe.call({
						method: "resource_management.api.resource_allocation.approve_request",
						args: {
							name: doc.name
						},
						callback: function(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Resource Allocation approved successfully"),
									indicator: 'green'
								});
								cur_list.refresh();
							}
						}
					});
				}
			);
		}
	},
	
	// Format rows to show more details
	formatters: {
		employee_name: function(value, df, doc) {
			return `<div>
						<div class="level-item bold">
							${value}
						</div>
						<div class="level-item">
							<span class="text-muted">
								${doc.employee}
							</span>
						</div>
					</div>`;
		},
		
		project_name: function(value, df, doc) {
			return `<div>
						<div class="level-item bold">
							${value}
						</div>
						<div class="level-item">
							<span class="text-muted">
								${doc.project}
							</span>
						</div>
					</div>`;
		},
		
		allocation_percentage: function(value) {
			return `<div class="progress" style="margin-bottom: 0; height: 12px;">
						<div class="progress-bar" role="progressbar" 
							aria-valuenow="${value}" 
							aria-valuemin="0" 
							aria-valuemax="100" 
							style="width: ${value}%; background-color: ${value > 80 ? '#ff5858' : '#5e64ff'};">
							${value}%
						</div>
					</div>`;
		}
	}
};
