# coverage helper
docker exec -it spotify-report-website-1 coverage run --branch -m pytest
docker exec -it spotify-report-website-1 coverage html
docker exec -it spotify-report-website-1 coverage xml
docker cp $(docker ps -aqf "name=spotify-report-website"):/opt/htmlcov/. ./htmlcov/.
docker cp $(docker ps -aqf "name=spotify-report-website"):/opt/coverage.xml ./coverage.xml
docker exec -it spotify-report-website-1 coverage report
