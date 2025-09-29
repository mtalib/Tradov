Interactive Brokers TWS API User Guide for Linux and Python
Overview
The Interactive Brokers Trader Workstation (TWS) API allows you to build custom trading applications in Python (and other languages) running on Linux. It is essential to note that the TWS API is a protocol for communicating with the running Trader Workstation software on your system. As such, the Trader Workstation must be running and logged in for the API to work properly.

Installing Trader Workstation (TWS) on Linux
Download TWS for Linux:

Go to the Interactive Brokers website and download the latest Linux installer script, typically named like tws-latest-linux-x86.sh.

Make the installer executable:
Open a terminal and navigate to the folder where you downloaded the installer (usually ~/Downloads):

bash
cd ~/Downloads
chmod u+x tws-latest-linux-x86.sh
Run the installer:

bash
sudo ./tws-latest-linux-x86.sh
Follow the interactive wizard to complete installation.

By default, TWS installs under your user home directory.

When finished, launch TWS either via your system menu or by running the TWS launcher found under ~/Jts/<version>/tws.

Log in to Trader Workstation:

Provide your IBKR account credentials in the GUI.

Choose between live or paper trading environments.

Keep the TWS application running and logged in continuously while using the API.

Installing the TWS API Python Client on Linux
Download the TWS API source:

Download the Mac/Unix zip file from the IBKR API page, named like twsapi_macunix.<version>.zip.

Unzip the archive:

bash
unzip twsapi_macunix.<version>.zip -d $HOME/
cd ~/IBJts/source/pythonclient/
Install the Python package:

bash
python3 setup.py install
This installs the ibapi package needed to develop Python TWS API applications.

To verify installation, run:

bash
python3 -m pip show ibapi
Configuring Trader Workstation for API Use
In TWS, go to File > Global Configuration.

Navigate to API > Settings.

Enable “Enable ActiveX and Socket Clients”.

Confirm the Socket port (usually 7496 for live, 7497 for paper).

Disable Read-Only API if you intend to place orders.

Apply and save to enable API access.

Managing Market Data for API-Only Use on Linux
If you want market data visible only on your private trading dashboard (via the API) and want to avoid using your TWS workstation's market data subscription lines, take these steps:

Log in to the IBKR Client Portal.

Navigate to Market Data Subscriptions.

For each region or exchange, set your subscription type to “Non-Display (API trading applications)”.

This configures the premium market data subscription lines to be used exclusively by your API applications, preventing TWS graphical interface from consuming them.

Save and confirm your changes.

Important Points
The Trader Workstation must be kept running and logged in at all times for your Python API application to connect and operate.

The API client communicates with TWS via a TCP socket on localhost.

Avoid simultaneously running multiple TWS or other IB platforms as it can cause connection conflicts.

Regularly update your TWS client and TWS API package to stay compatible and stable.

For development and debugging, enable API logging inside TWS.

Use Python 3.x and ensure your system environment has required modules (setuptools etc.) for smooth installation.

When writing your client code, ensure you use the correct port matching the TWS configuration.

Summary
This guide has detailed how to install and configure Interactive Brokers Trader Workstation and the Python TWS API client on Linux. The fundamental requirement is that the Trader Workstation must be running and logged in while your Python API scripts connect to it for automated trading or data retrieval. Managing market data subscriptions as "Non-Display" in the IBKR Client Portal ensures dedicated data feeds for your API without visual interference from TWS GUI.

For more examples and detailed API programming guides, visit the official Interactive Brokers API documentation and IBKR Campus tutorials.

This guide provides a stable foundation for Linux users developing Python automation on Interactive Brokers via the TWS API.
