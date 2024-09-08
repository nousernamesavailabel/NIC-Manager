from elevate import elevate
import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QListWidget, QTextEdit, QLineEdit, QPushButton, \
    QFormLayout, QMessageBox, QRadioButton, QButtonGroup, QHBoxLayout

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
    """Use netsh to get detailed information about the selected NIC, including MTU."""
    try:
        print(f"[DEBUG] Running 'netsh interface ipv4 show config {interface}'")  # DEBUG
        output = subprocess.run(["netsh", "interface", "ipv4", "show", "config", interface], capture_output=True,
                                text=True).stdout
        print(f"[DEBUG] netsh output for {interface} config:\n{output}")  # DEBUG

        nic_details = {}

        # Parse netsh output
        lines = output.splitlines()
        ip_address = None
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
            elif "Statically Configured DNS Servers" in line:
                dns_servers = line.split(":")[-1].strip().split()
                nic_details['Primary DNS'] = dns_servers[0] if len(dns_servers) > 0 else ""
                nic_details['Backup DNS'] = dns_servers[1] if len(dns_servers) > 1 else ""
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
        print(
            f"[DEBUG] Running netsh to set static IP: {ip}, Subnet Mask: {subnet_mask}, Gateway: {gateway} for {interface}")
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
        QMessageBox.information(None, "Success",
                                "IP address, Subnet Mask, Default Gateway, and DNS successfully changed.")
    except Exception as e:
        print(f"[ERROR] Failed to set static IP: {e}")
        QMessageBox.critical(None, "Error", f"Failed to set the new configuration: {str(e)}")


def set_dhcp(interface):
    """Set the interface to use DHCP."""
    try:
        print(f"[DEBUG] Running netsh to set DHCP for {interface}")
        command = f'netsh interface ipv4 set address name="{interface}" source=dhcp'
        result = subprocess.run(command, capture_output=True, text=True, shell=True)

        if result.returncode != 0:
            raise Exception(result.stderr)

        print("[DEBUG] Successfully set DHCP")
        QMessageBox.information(None, "Success", "Successfully changed to DHCP.")
    except Exception as e:
        print(f"[ERROR] Failed to set DHCP: {e}")
        QMessageBox.critical(None, "Error", f"Failed to set DHCP: {str(e)}")


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


class NICViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """Initialize the GUI components."""
        self.setWindowTitle('NIC Manager')
        self.setGeometry(300, 300, 500, 650)

        layout = QVBoxLayout()

        label = QLabel('Network Interface Cards (NICs) on this machine:')
        layout.addWidget(label)

        self.nic_list = QListWidget()
        self.nic_list.clicked.connect(self.show_nic_details)
        layout.addWidget(self.nic_list)

        # Create a text area to display NIC details
        self.nic_details = QTextEdit()
        self.nic_details.setReadOnly(True)
        layout.addWidget(self.nic_details)

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
        layout.addLayout(radio_layout)

        # Form for static IP modification
        self.ip_input = QLineEdit(self)
        self.subnet_input = QLineEdit(self)
        self.gateway_input = QLineEdit(self)
        self.primary_dns_input = QLineEdit(self)
        self.backup_dns_input = QLineEdit(self)
        self.mtu_input = QLineEdit(self)
        self.submit_button = QPushButton("Apply Changes", self)
        self.submit_button.clicked.connect(self.apply_changes)

        # Add input fields to the form layout
        form_layout = QFormLayout()
        form_layout.addRow("IP Address:", self.ip_input)
        form_layout.addRow("Subnet Mask:", self.subnet_input)
        form_layout.addRow("Default Gateway:", self.gateway_input)
        form_layout.addRow("Primary DNS:", self.primary_dns_input)
        form_layout.addRow("Backup DNS:", self.backup_dns_input)
        form_layout.addRow("MTU:", self.mtu_input)
        form_layout.addRow(self.submit_button)
        layout.addLayout(form_layout)

        self.setLayout(layout)

        # Populate NIC names
        print("[DEBUG] Retrieving NIC names")  # DEBUG
        nic_names = get_nic_names()
        for nic in nic_names:
            print(f"[DEBUG] Adding NIC to list: {nic}")  # DEBUG
            self.nic_list.addItem(nic)

        self.current_nic = None

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
        """Display the NIC details when an interface is clicked."""
        try:
            selected_nic = self.nic_list.currentItem().text()
            print(f"[DEBUG] Selected NIC: {selected_nic}")  # DEBUG
            nic_details = get_nic_details(selected_nic)
            self.current_nic = selected_nic

            # Format the details for display
            details_text = f"Details for {selected_nic}:\n"
            for key, value in nic_details.items():
                details_text += f"{key}: {value}\n"

            print(f"[DEBUG] Displaying NIC details:\n{details_text}")  # DEBUG
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
            else:
                self.dhcp_radio.setChecked(True)

        except Exception as e:
            print(f"[ERROR] Failed to show NIC details: {e}")
            QMessageBox.critical(self, "Error", f"Failed to display NIC details: {str(e)}")

    def apply_changes(self):
        """Apply new static IP, DHCP, or MTU settings based on user selection."""
        try:
            mtu_value = self.mtu_input.text()
            if mtu_value:
                set_mtu(self.current_nic, mtu_value)

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
        except Exception as e:
            print(f"[ERROR] Failed to apply changes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply changes: {str(e)}")


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    viewer = NICViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
