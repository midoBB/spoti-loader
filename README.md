
```bash
apt-get install python3-dev python3-pip python3-distutils unrar unzip
```
```bash
curl -sSL https://install.python-poetry.org | python3 -
```
```bash
wget https://github.com/midoBB/spoti-loader/releases/latest/download/spotiloader_armv7.zip
```


1. Create the `spotiloader` directory

    ```shell
    sudo mkdir /opt/spotiloader
    ```

1. Extract the content of the zipped release to the previously created `spotiloader` directory

    ```shell
    sudo unzip spotiloader_armv7.zip -d /opt/spotiloader
    ```

1. cd into /opt/spotiloader

    ```shell
    cd /opt/spotiloader
    ```

1. Install the Python requirements:

    ```python
    poetry install
    ```
1. Change ownership to your preferred user for running programs (replace both instances of `$USER`, or leave it to change ownership to current user)

    ```bash
    sudo chown -R $USER:$USER /opt/spotiloader
    ```

1. You can now start spotiloader using the following command:

    ```python
    poetry run python3 spoti_loader/main.py
    ```
1. You can add a service file
```bash
sudo vim /etc/systemd/system/spotiloader.service
```
Copy and past this to the file
```ini
[Unit]
Description=Spotiloader Daemon
After=syslog.target network.target

[Service]
WorkingDirectory=/opt/spotiloader/
User=your_user
Group=your_group
UMask=0002
Restart=on-failure
RestartSec=5
Type=simple
ExecStart=poetry run python3 spoti_loader/main.py
KillSignal=SIGINT
TimeoutStopSec=20
SyslogIdentifier=Spotiloader

[Install]
WantedBy=multi-user.target
```
```bash
sudo vim /etc/systemd/system/spotiloader.timer
```
Copy and past this to the file
```ini
[Unit]
Description=Run Spotiloader daily at 7 am

[Timer]
OnCalendar=daily
At=07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

1. Reload the configuration
```bash
sudo systemctl daemon-reload
```

1. Enable and start the timers
```bash
sudo systemctl enable spotiloader.timer
sudo systemctl start spotiloader.timer
```
