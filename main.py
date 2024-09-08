from elevate import elevate
import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QListWidget, QTextEdit, QLineEdit, QPushButton, \
    QFormLayout, QMessageBox, QRadioButton, QButtonGroup, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem


# Automatically request elevated privileges
elevate()

def get_nic_names():
    """Use netsh to get network interface names."""
    try:
        print("[DEBUG] Running 'netsh interface ipv4 show interfaces'")  # DEBUG
        output = subprocess.run(["netsh", "interface", "ipv4", "show", "interfaces"], capture_output=True,
                                text=True).stdout
        print(f"[DEBUG] netsh output for interfaces:\n{output}")  # DEBUG

        lines = output.splitlines()
        interface_names = []

        for line in lines:
            if "connected" in line.lower():  # Only include connected interfaces
                parts = line.split()
                print(f"[DEBUG] Parsing line for interface: {line}")  # DEBUG
                if len(parts) > 4:  # Ensure there's enough parts to extract name
                    interface_name = " ".join(parts[4:])  # Join parts after index to get full name
                    interface_names.append(interface_name)
                    print(f"[DEBUG] Found interface: {interface_name}")  # DEBUG

        print(f"[DEBUG] Interface names found: {interface_names}")  # DEBUG
        return interface_names
    except Exception as e:
        print(f"[ERROR] Failed to retrieve NIC names: {e}")
        QMessageBox.critical(None, "Error", f"Failed to retrieve NIC names: {str(e)}")
        return []

def get_mtu(interface):
    """Use netsh to get the MTU for the specified interface."""
    try:
        print(f"[DEBUG] Running 'netsh interface ipv4 show subinterface'")  # DEBUG
        output = subprocess.run(["netsh", "interface", "ipv4", "show", "subinterface"], capture_output=True,
                                text=True).stdout
        print(f"[DEBUG] netsh output for subinterfaces:\n{output}")  # DEBUG

        lines = output.splitlines()
        mtu_value = None

        for line in lines:
            if interface in line:
                parts = line.split()
                if len(parts) > 2:
                    mtu_value = parts[0]  # MTU is the first item in the line
                    print(f"[DEBUG] Found MTU for {interface}: {mtu_value}")
                    break

        return mtu_value if mtu_value else "Unknown"
    except Exception as e:
        print(f"[ERROR] Failed to retrieve MTU: {e}")
        return "Unknown"

def get_nic_details(interface):
    """Use netsh to get detailed information about the selected NIC, including DNS and MTU."""
    try:
        print(f"[DEBUG] Running 'netsh interface ipv4 show config {interface}'")  # DEBUG
        output = subprocess.run(["netsh", "interface", "ipv4", "show", "config", interface], capture_output=True,
                                text=True).stdout
        print(f"[DEBUG] netsh output for {interface} config:\n{output}")  # DEBUG

        nic_details = {}

        # Parse netsh output
        lines = output.splitlines()
        ip_address = None
        primary_dns = None
        backup_dns = None
        for line in lines:
            if "IP Address" in line:
                ip_address = line.split(":")[-1].strip()
                nic_details['IP Address'] = ip_address
                print(f"[DEBUG] Found IP Address: {ip_address}")  # DEBUG
            elif "Subnet Prefix" in line:
                # Split to get the subnet mask portion
                subnet_prefix = line.split(":")[-1].strip()
                subnet_mask = subnet_prefix.split(" ")[-1]
                subnet_mask = subnet_mask[:-1]
                nic_details['Subnet Mask'] = subnet_mask
                print(f"[DEBUG] Found Subnet Mask: {nic_details['Subnet Mask']}")  # DEBUG
            elif "Default Gateway" in line:
                nic_details['Default Gateway'] = line.split(":")[-1].strip() or "No gateway"
                print(f"[DEBUG] Found Default Gateway: {nic_details['Default Gateway']}")  # DEBUG
            elif "Statically Configured DNS Servers" in line or "DNS servers configured through DHCP" in line:
                # Extract DNS servers
                dns_servers = line.split(":")[-1].strip().split()
                nic_details['Primary DNS'] = dns_servers[0] if len(dns_servers) > 0 else "None"
                nic_details['Backup DNS'] = dns_servers[1] if len(dns_servers) > 1 else "None"
                print(f"[DEBUG] Found DNS Servers: {nic_details['Primary DNS']}, {nic_details['Backup DNS']}")  # DEBUG
            elif "DHCP enabled" in line:
                nic_details['DHCP'] = line.split(":")[-1].strip()
                print(f"[DEBUG] Found DHCP status: {nic_details['DHCP']}")  # DEBUG

        # Get MTU from the subinterface command
        mtu_value = get_mtu(interface)
        nic_details['MTU'] = mtu_value

        print(f"[DEBUG] NIC details for {interface}: {nic_details}")  # DEBUG
        return nic_details
    except Exception as e:
        print(f"[ERROR] Failed to retrieve NIC details: {e}")
        QMessageBox.critical(None, "Error", f"Failed to retrieve NIC details for {interface}: {str(e)}")
        return {}

def set_static_ip(interface, ip, subnet_mask, gateway, primary_dns, backup_dns):
    """Set a new static IP, subnet mask, default gateway, and DNS using netsh."""
    try:
        print(f"[DEBUG] Running netsh to set static IP: {ip}, Subnet Mask: {subnet_mask}, Gateway: {gateway} for {interface}")
        command = f'netsh interface ipv4 set address name="{interface}" static {ip} {subnet_mask} {gateway}' if gateway else f'netsh interface ipv4 set address name="{interface}" static {ip} {subnet_mask} none'

        result = subprocess.run(command, capture_output=True, text=True, shell=True)

        if result.returncode != 0:
            error_message = result.stderr.strip()
            raise Exception(f"Failed with error: {error_message}")

        # If DNS fields are not empty, apply them
        if primary_dns or backup_dns:
            dns_command = f'netsh interface ipv4 set dns name="{interface}" static {primary_dns} primary'
            subprocess.run(dns_command, capture_output=True, text=True, shell=True)
            if backup_dns:
                backup_dns_command = f'netsh interface ipv4 add dns name="{interface}" {backup_dns} index=2'
                subprocess.run(backup_dns_command, capture_output=True, text=True, shell=True)

        print("[DEBUG] Successfully set the new static IP configuration")
        QMessageBox.information(None, "Success", "IP address, Subnet Mask, Default Gateway, and DNS successfully changed.")
    except Exception as e:
        print(f"[ERROR] Failed to set static IP: {e}")
        QMessageBox.critical(None, "Error", f"Failed to set the new configuration: {str(e)}")

def set_dhcp(interface):
    """Set the interface to use DHCP and set DNS to automatic."""
    try:
        print(f"[DEBUG] Running netsh to set DHCP for {interface}")
        command = f'netsh interface ipv4 set address name="{interface}" source=dhcp'
        result = subprocess.run(command, capture_output=True, text=True, shell=True)

        if result.returncode != 0:
            raise Exception(result.stderr)

        # Set DNS to be obtained automatically as well
        print(f"[DEBUG] Running netsh to set DNS to automatic for {interface}")
        dns_command = f'netsh interface ipv4 set dns name="{interface}" source=dhcp'
        dns_result = subprocess.run(dns_command, capture_output=True, text=True, shell=True)

        if dns_result.returncode != 0:
            raise Exception(dns_result.stderr)

        print("[DEBUG] Successfully set DHCP and DNS to automatic")
        QMessageBox.information(None, "Success", "Successfully changed to DHCP and automatic DNS.")
    except Exception as e:
        print(f"[ERROR] Failed to set DHCP or DNS: {e}")
        QMessageBox.critical(None, "Error", f"Failed to set DHCP or DNS: {str(e)}")

def set_mtu(interface, mtu_value):
    """Set the MTU for the specified interface using netsh."""
    try:
        print(f"[DEBUG] Running netsh to set MTU: {mtu_value} for {interface}")
        mtu_command = f'netsh interface ipv4 set subinterface "{interface}" mtu={mtu_value} store=persistent'
        result = subprocess.run(mtu_command, capture_output=True, text=True, shell=True)

        if result.returncode != 0:
            error_message = result.stderr.strip()
            raise Exception(f"Failed with error: {error_message}")

        print("[DEBUG] Successfully set MTU")
        QMessageBox.information(None, "Success", f"MTU successfully set to {mtu_value}.")
    except Exception as e:
        print(f"[ERROR] Failed to set MTU: {e}")
        QMessageBox.critical(None, "Error", f"Failed to set MTU: {str(e)}")

def get_routing_table():
    """Run 'route print', extract the IPv4 Route Table, and return the output."""
    try:
        print(f"[DEBUG] Running 'route print' to get the routing table")  # DEBUG
        output = subprocess.run(["route", "print"], capture_output=True, text=True).stdout
        print(f"[DEBUG] Full routing table:\n{output}")  # DEBUG

        # Extract the IPv4 Route Table section
        ipv4_table = []
        inside_ipv4_table = False
        inside_active_routes = False

        for line in output.splitlines():
            # Start parsing once we encounter "Active Routes:"
            if "Active Routes:" in line:
                inside_active_routes = True
                continue  # Skip the "Active Routes:" line itself

            # Stop parsing at the end of the route table section
            if "===" in line and inside_active_routes:
                break  # End of IPv4 route table

            if inside_active_routes:
                # Skip the header line with "Network Destination", "Netmask", etc.
                if "Network Destination" in line:
                    continue
                if line.strip():  # Skip empty lines
                    ipv4_table.append(line)

        print(f"[DEBUG] Extracted IPv4 routing table:\n{ipv4_table}")  # DEBUG
        return ipv4_table
    except Exception as e:
        print(f"[ERROR] Failed to retrieve routing table: {e}")
        QMessageBox.critical(None, "Error", f"Failed to retrieve routing table: {str(e)}")
        return []


class NICViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """Initialize the GUI components."""
        self.setWindowTitle('NIC Manager')
        self.setGeometry(300, 300, 475, 500)

        layout = QVBoxLayout()

        # Create a tab widget to hold multiple tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: Network Interface Cards
        self.nic_tab = QWidget()
        self.init_nic_tab()
        self.tabs.addTab(self.nic_tab, "NIC Details")

        # Tab 2: Routing Table
        self.routing_tab = QWidget()
        self.init_routing_tab()
        self.tabs.addTab(self.routing_tab, "Routing Table")

        self.setLayout(layout)

    def init_nic_tab(self):
        """Initialize the NIC tab components."""
        nic_layout = QVBoxLayout()

        label = QLabel('Network Interface Cards (NICs) on this machine:')
        nic_layout.addWidget(label)

        self.nic_list = QListWidget()
        self.nic_list.clicked.connect(self.show_nic_details)
        nic_layout.addWidget(self.nic_list)

        # Create a text area to display NIC details
        self.nic_details = QTextEdit()
        self.nic_details.setReadOnly(True)
        nic_layout.addWidget(self.nic_details)

        # Radio buttons for DHCP and Static
        self.dhcp_radio = QRadioButton("DHCP", self)
        self.static_radio = QRadioButton("Static", self)
        self.radio_group = QButtonGroup(self)
        self.radio_group.addButton(self.dhcp_radio)
        self.radio_group.addButton(self.static_radio)

        self.dhcp_radio.toggled.connect(self.on_radio_toggle)

        # Horizontal layout for radio buttons
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.dhcp_radio)
        radio_layout.addWidget(self.static_radio)
        nic_layout.addLayout(radio_layout)

        # Form for static IP modification
        self.ip_input = QLineEdit(self)
        self.subnet_input = QLineEdit(self)
        self.gateway_input = QLineEdit(self)
        self.primary_dns_input = QLineEdit(self)
        self.backup_dns_input = QLineEdit(self)
        self.submit_button = QPushButton("Apply Network Settings", self)
        self.submit_button.clicked.connect(self.apply_network_settings)

        # Add input fields for network settings to the form layout
        form_layout = QFormLayout()
        form_layout.addRow("IP Address:", self.ip_input)
        form_layout.addRow("Subnet Mask:", self.subnet_input)
        form_layout.addRow("Default Gateway:", self.gateway_input)
        form_layout.addRow("Primary DNS:", self.primary_dns_input)
        form_layout.addRow("Backup DNS:", self.backup_dns_input)
        form_layout.addRow(self.submit_button)
        nic_layout.addLayout(form_layout)

        # MTU settings with a separate apply button
        self.mtu_input = QLineEdit(self)
        self.mtu_button = QPushButton("Apply MTU", self)
        self.mtu_button.clicked.connect(self.apply_mtu)

        # Add input field for MTU to the form layout
        mtu_layout = QFormLayout()
        mtu_layout.addRow("MTU:", self.mtu_input)
        mtu_layout.addRow(self.mtu_button)
        nic_layout.addLayout(mtu_layout)

        self.nic_tab.setLayout(nic_layout)

        # Populate NIC names
        print("[DEBUG] Retrieving NIC names")  # DEBUG
        nic_names = get_nic_names()
        for nic in nic_names:
            print(f"[DEBUG] Adding NIC to list: {nic}")  # DEBUG
            self.nic_list.addItem(nic)

        self.current_nic = None

    def init_routing_tab(self):
        """Initialize the routing table tab components."""
        routing_layout = QVBoxLayout()

        label = QLabel('Windows Routing Table:')
        routing_layout.addWidget(label)

        # Create a table widget to display the routing table
        self.routing_table_widget = QTableWidget()
        self.routing_table_widget.setColumnCount(5)
        self.routing_table_widget.setHorizontalHeaderLabels(
            ['Network Destination', 'Netmask', 'Gateway', 'Interface', 'Metric'])
        routing_layout.addWidget(self.routing_table_widget)

        # Create entry boxes for adding/deleting routes
        self.destination_input = QLineEdit(self)
        self.netmask_input = QLineEdit(self)
        self.gateway_input = QLineEdit(self)
        self.metric_input = QLineEdit(self)

        # Form layout for the route inputs
        route_form_layout = QFormLayout()
        route_form_layout.addRow("Network Destination:", self.destination_input)
        route_form_layout.addRow("Netmask:", self.netmask_input)
        route_form_layout.addRow("Gateway:", self.gateway_input)
        route_form_layout.addRow("Metric:", self.metric_input)
        routing_layout.addLayout(route_form_layout)

        # Add and Delete buttons
        self.add_button = QPushButton("Add Route", self)
        self.delete_button = QPushButton("Delete Route", self)

        self.add_button.clicked.connect(self.add_route)
        self.delete_button.clicked.connect(self.delete_route)

        # Horizontal layout for buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.delete_button)
        routing_layout.addLayout(button_layout)

        self.routing_tab.setLayout(routing_layout)

        # Populate the routing table when the tab is displayed
        self.populate_routing_table()

    def populate_routing_table(self):
        """Populate the routing table in the routing tab."""
        try:
            ipv4_table = get_routing_table()

            # Filter and add routes to the table
            if ipv4_table:
                self.routing_table_widget.setRowCount(len(ipv4_table))  # Set row count based on valid rows
                row_index = 0
                for line in ipv4_table:
                    # Split the line, handling multiple spaces as field delimiters
                    parts = line.split()

                    # Ensure we have at least 5 fields for each line, add empty placeholders if necessary
                    while len(parts) < 5:
                        parts.append('')

                    # Populate the table with Network Destination, Netmask, Gateway, Interface, Metric
                    self.routing_table_widget.setItem(row_index, 0, QTableWidgetItem(parts[0]))  # Network Destination
                    self.routing_table_widget.setItem(row_index, 1, QTableWidgetItem(parts[1]))  # Netmask
                    self.routing_table_widget.setItem(row_index, 2, QTableWidgetItem(parts[2]))  # Gateway
                    self.routing_table_widget.setItem(row_index, 3, QTableWidgetItem(parts[3]))  # Interface
                    self.routing_table_widget.setItem(row_index, 4, QTableWidgetItem(parts[4]))  # Metric
                    row_index += 1

                    # Automatically resize columns to fit the contents
                    self.routing_table_widget.resizeColumnsToContents()

        except Exception as e:
            print(f"[ERROR] Failed to populate routing table: {e}")
            QMessageBox.critical(self, "Error", f"Failed to populate routing table: {str(e)}")

    def add_route(self):
        """Add a new route to the Windows routing table using 'route add'."""
        try:
            destination = self.destination_input.text()
            netmask = self.netmask_input.text()
            gateway = self.gateway_input.text()
            metric = self.metric_input.text()

            if not destination or not netmask or not gateway:
                raise ValueError("Network Destination, Netmask, and Gateway are required.")

            command = f'route add {destination} mask {netmask} {gateway} metric {metric}'
            print(f"[DEBUG] Running command: {command}")  # DEBUG
            result = subprocess.run(command, capture_output=True, text=True, shell=True)

            if result.returncode != 0:
                raise Exception(result.stderr)

            print("[DEBUG] Route successfully added")
            QMessageBox.information(self, "Success", "Route successfully added.")

            # Refresh the routing table after adding the route
            self.populate_routing_table()

        except Exception as e:
            print(f"[ERROR] Failed to add route: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add route: {str(e)}")

    def delete_route(self):
        """Delete a route from the Windows routing table using 'route delete'."""
        try:
            destination = self.destination_input.text()
            netmask = self.netmask_input.text()

            if not destination or not netmask:
                raise ValueError("Network Destination and Netmask are required for deletion.")

            command = f'route delete {destination} mask {netmask}'
            print(f"[DEBUG] Running command: {command}")  # DEBUG
            result = subprocess.run(command, capture_output=True, text=True, shell=True)

            if result.returncode != 0:
                raise Exception(result.stderr)

            print("[DEBUG] Route successfully deleted")
            QMessageBox.information(self, "Success", "Route successfully deleted.")

            # Refresh the routing table after deleting the route
            self.populate_routing_table()

        except Exception as e:
            print(f"[ERROR] Failed to delete route: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete route: {str(e)}")

    def on_radio_toggle(self):
        """Enable or disable fields based on selected radio button."""
        if self.static_radio.isChecked():
            self.ip_input.setEnabled(True)
            self.subnet_input.setEnabled(True)
            self.gateway_input.setEnabled(True)
            self.primary_dns_input.setEnabled(True)
            self.backup_dns_input.setEnabled(True)
            self.mtu_input.setEnabled(True)
            self.submit_button.setEnabled(True)
        else:
            # DHCP selected, disable static fields except MTU
            self.ip_input.setEnabled(False)
            self.subnet_input.setEnabled(False)
            self.gateway_input.setEnabled(False)
            self.primary_dns_input.setEnabled(False)
            self.backup_dns_input.setEnabled(False)
            self.mtu_input.setEnabled(True)

    def show_nic_details(self):
        """Display the NIC details when an interface is clicked or updated."""
        try:
            selected_nic = self.nic_list.currentItem().text()  # Retrieve the selected NIC directly from the list
            self.current_nic = selected_nic  # Ensure the current NIC is set
            print(f"[DEBUG] Refreshing details for NIC: {self.current_nic}")  # DEBUG

            # Call get_nic_details to retrieve NIC details
            nic_details = get_nic_details(self.current_nic)

            if not nic_details:
                raise ValueError(f"No NIC details were retrieved for interface: {self.current_nic}")

            # Format the details for display
            details_text = f"Details for {self.current_nic}:\n"
            for key, value in nic_details.items():
                details_text += f"{key}: {value}\n"

            print(f"[DEBUG] Displaying updated NIC details:\n{details_text}")  # DEBUG
            self.nic_details.setText(details_text)

            # Enable input fields and radio buttons based on DHCP or static
            if nic_details.get('DHCP', 'Yes') == 'No':
                self.static_radio.setChecked(True)
                self.ip_input.setText(nic_details.get('IP Address', ''))
                self.subnet_input.setText(nic_details.get('Subnet Mask', ''))
                self.gateway_input.setText(nic_details.get('Default Gateway', ''))
                self.primary_dns_input.setText(nic_details.get('Primary DNS', ''))
                self.backup_dns_input.setText(nic_details.get('Backup DNS', ''))
                self.mtu_input.setText(nic_details.get('MTU', ''))

                # Enable fields for static IP
                self.ip_input.setEnabled(True)
                self.subnet_input.setEnabled(True)
                self.gateway_input.setEnabled(True)
                self.primary_dns_input.setEnabled(True)
                self.backup_dns_input.setEnabled(True)
            else:
                self.dhcp_radio.setChecked(True)
                self.ip_input.setText(nic_details.get('IP Address', ''))
                self.subnet_input.setText(nic_details.get('Subnet Mask', ''))
                self.gateway_input.setText(nic_details.get('Default Gateway', ''))
                self.primary_dns_input.setText(nic_details.get('Primary DNS', ''))
                self.backup_dns_input.setText(nic_details.get('Backup DNS', ''))
                self.mtu_input.setText(nic_details.get('MTU', ''))

                # Disable fields for DHCP
                self.ip_input.setEnabled(False)
                self.subnet_input.setEnabled(False)
                self.gateway_input.setEnabled(False)
                self.primary_dns_input.setEnabled(False)
                self.backup_dns_input.setEnabled(False)

            # MTU is always editable
            self.mtu_input.setEnabled(True)

        except Exception as e:
            print(f"[ERROR] Failed to show NIC details: {e}")
            QMessageBox.critical(self, "Error", f"Failed to display NIC details: {str(e)}")

    def apply_network_settings(self):
        """Apply new static IP, DHCP, and DNS settings based on user selection."""
        try:
            if self.dhcp_radio.isChecked():
                set_dhcp(self.current_nic)
            else:
                new_ip = self.ip_input.text()
                new_subnet = self.subnet_input.text()
                new_gateway = self.gateway_input.text()
                primary_dns = self.primary_dns_input.text()
                backup_dns = self.backup_dns_input.text()

                # Validate that IP and Subnet are not empty, but allow empty Gateway and DNS
                if not new_ip or not new_subnet:
                    raise ValueError("IP Address and Subnet Mask cannot be empty.")

                set_static_ip(self.current_nic, new_ip, new_subnet, new_gateway, primary_dns, backup_dns)

            # After applying changes, refresh the NIC details
            self.show_nic_details()

        except Exception as e:
            print(f"[ERROR] Failed to apply network settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply network settings: {str(e)}")

    def apply_mtu(self):
        """Apply the MTU settings."""
        try:
            mtu_value = self.mtu_input.text()
            if mtu_value:
                set_mtu(self.current_nic, mtu_value)

            # After applying changes, refresh the NIC details
            self.show_nic_details()

        except Exception as e:
            print(f"[ERROR] Failed to apply MTU: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply MTU: {str(e)}")

def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    viewer = NICViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
