sudo apt -y update
sudo apt install -y wget curl unzip
wget http://archive.ubuntu.com/ubuntu/pool/main/libu/libu2f-host/libu2f-udev_1.1.4-1_all.deb
sudo dpkg -i libu2f-udev_1.1.4-1_all.deb
wget http://dl.google.com/linux/deb/pool/main/g/google-chrome-unstable/google-chrome-unstable_114.0.5735.6-1_amd64.deb
sudo apt-get install -f ./google-chrome-unstable_114.0.5735.6-1_amd64.deb
sudo ln -s /opt/google/chrome-unstable/google-chrome google-chrome-stable
CHROME_DRIVER_VERSION=114.0.5735.90
sudo wget -N https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip -P /tmp/
sudo unzip -o /tmp/chromedriver_linux64.zip -d /tmp/
sudo chmod +x /tmp/chromedriver
sudo mv /tmp/chromedriver /usr/local/bin/chromedriver
pip install selenium chromedriver_autoinstaller requests beautifulsoup4

pip install chromedriver_autoinstaller kaleido python-multipart fastapi nest-asyncio pyngrok uvicorn
pip install -U sentence-transformers gensim transformers gspread pandas numpy
