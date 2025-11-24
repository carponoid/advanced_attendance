frappe.ui.form.on('Biometric Device Settings', {
    refresh: function(frm) {
        // Avoid adding multiple buttons on repeated refresh
        if (!frm.custom_test_connection_button_added) {
            frm.add_custom_button(
                'Test Connection',
                function() {
                    if (!frm.doc.device_ip || !frm.doc.device_port) {
                        frappe.msgprint('Please set Device IP Address and Device Port before testing.');
                        return;
                    }
                    frappe.call({
                        method: 'advanced_attendance.zkteco_connector.test_device_connection',
                        args: {
                            device_ip: frm.doc.device_ip,
                            device_port: frm.doc.device_port
                        },
                        freeze: true,
                        freeze_message: 'Testing connection to device...',
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: r.message.message || 'Successfully connected to device.',
                                    indicator: 'green'
                                });
                            } else {
                                let err = (r.message && (r.message.error || r.message.message)) || 'Connection failed.';
                                frappe.show_alert({
                                    message: 'Connection failed: ' + err,
                                    indicator: 'red'
                                });
                            }
                        },
                        error: function(err) {
                            frappe.show_alert({
                                message: 'Connection test failed: ' + (err.message || ''),
                                indicator: 'red'
                            });
                        }
                    });
                },
                'Actions' // Button group
            );
            frm.custom_test_connection_button_added = true;
        }
    }
});
