# coverage helper
docker exec -it spotify-report-website-1 coverage run -m pytest
docker exec -it spotify-report-website-1 coverage html
docker cp $(docker ps -aqf "name=spotify-report-website"):/opt/htmlcov ./htmlcov
