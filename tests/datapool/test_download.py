import requests


def test_data_availability():
    url = "https://owncloud.fraunhofer.de/index.php/s/McrHKZ62ci0FxCN/download?path=%2F&files=core/"
    response = requests.head(url, timeout=10)  # Verwende HEAD, um nur die Header abzurufen
    assert response.status_code == 200, f"Data Repo is not available: {response.status_code}"
