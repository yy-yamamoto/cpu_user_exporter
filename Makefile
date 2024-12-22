# Makefile for installing and managing the CPU User Exporter

# Default Variables (ユーザーが指定しない場合に使われるデフォルト値)
INTERVAL ?= 15
GRACE_PERIOD ?= 60
CPU_THRESHOLD ?= 5.0
PORT ?= 8010
EXCLUDE_SYSTEM_USERS ?= true

# Fixed Variables
INSTALL_DIR=/opt/cpu_user_exporter
SERVICE_FILE=/etc/systemd/system/cpu_user_exporter.service
LOCAL_SERVICE_FILE=cpu_user_exporter.service
PYTHON=python3
SCRIPT=cpu_user_exporter.py

# Commands
.PHONY: all install clean uninstall enable disable

all: install

install:
	@echo "Installing CPU User Exporter..."
	@echo "Using parameters:"
	@echo "  INTERVAL=$(INTERVAL)"
	@echo "  GRACE_PERIOD=$(GRACE_PERIOD)"
	@echo "  CPU_THRESHOLD=$(CPU_THRESHOLD)"
	@echo "  PORT=$(PORT)"
	@echo "  EXCLUDE_SYSTEM_USERS=$(EXCLUDE_SYSTEM_USERS)"

	# Prepare exclude flag based on EXCLUDE_SYSTEM_USERS
	EXCLUDE_FLAG=
ifneq ($(EXCLUDE_SYSTEM_USERS),false)
	EXCLUDE_FLAG=--exclude-system-users
endif

	# Create installation directory
	mkdir -p $(INSTALL_DIR)
	# Copy the script to the installation directory
	cp $(SCRIPT) $(INSTALL_DIR)/
	chmod +x $(INSTALL_DIR)/$(SCRIPT)

	# Copy requirements.txt if it exists
	if [ -f requirements.txt ]; then cp requirements.txt $(INSTALL_DIR)/; fi

	# Create virtual environment and install dependencies
	$(PYTHON) -m venv $(INSTALL_DIR)/venv
	$(INSTALL_DIR)/venv/bin/pip install --upgrade pip
	if [ -f $(INSTALL_DIR)/requirements.txt ]; then \
	    $(INSTALL_DIR)/venv/bin/pip install -r $(INSTALL_DIR)/requirements.txt; \
	fi

	# Copy the service file from the current directory
	@echo "Installing systemd service file..."
	cp $(LOCAL_SERVICE_FILE) $(SERVICE_FILE)

	# Adjust systemd service file to use virtual environment and set variables
	# If $(EXCLUDE_FLAG) is empty, it is not added, and is only inserted if "--exclude-system-users" is desired.
	sed -i 's|ExecStart=.*|ExecStart=$(INSTALL_DIR)/venv/bin/python $(INSTALL_DIR)/$(SCRIPT) \
	--interval $(INTERVAL) --grace-period $(GRACE_PERIOD) \
	--cpu-threshold $(CPU_THRESHOLD) --port $(PORT) $(EXCLUDE_FLAG)|' $(SERVICE_FILE)

	# Reload systemd and enable the service
	@echo "Enabling CPU User Exporter service..."
	systemctl daemon-reload
	systemctl enable $(LOCAL_SERVICE_FILE)
	systemctl start $(LOCAL_SERVICE_FILE)
	@echo "CPU User Exporter installed and running."

clean:
	@echo "Cleaning up installation..."
	# Stop the service if running
	-systemctl stop $(LOCAL_SERVICE_FILE)
	# Remove the installation directory
	-rm -rf $(INSTALL_DIR)
	# Remove the systemd service file
	-rm -f $(SERVICE_FILE)
	# Reload systemd
	-systemctl daemon-reload
	@echo "Cleaned up CPU User Exporter installation."

uninstall: clean

enable:
	@echo "Enabling CPU User Exporter service..."
	systemctl enable $(LOCAL_SERVICE_FILE)
	systemctl start $(LOCAL_SERVICE_FILE)
	@echo "CPU User Exporter service enabled."

disable:
	@echo "Disabling CPU User Exporter service..."
	systemctl disable $(LOCAL_SERVICE_FILE)
	systemctl stop $(LOCAL_SERVICE_FILE)
	@echo "CPU User Exporter service disabled."
