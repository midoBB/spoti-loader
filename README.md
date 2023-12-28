## (Ubuntu / Debian) Install requirements with

  ```bash
  apt-get install python3-dev python3-pip python3-distutils unrar unzip
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
    python3 -m pip install -r requirements.txt
    ```
1. Change ownership to your preferred user for running programs (replace both instances of `$USER`, or leave it to change ownership to current user)

    ```bash
    sudo chown -R $USER:$USER /opt/spotiloader
    ```

1. You can now start spotiloader using the following command:

    ```python
    python3 spotiloader.py
    ```
