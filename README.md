# Newspaper delivery
Send an email each morning with the newspaper of the day in pdf. Made for the Swiss newspaper "Le Temps" https://www.letemps.ch/.

## How does it work?
- Receives a trigger at 5:00 a.m. each morning
- Login to https://www.letemps.ch/
- Generate the url to the newspaper of the current day
- Download (in memory) the pdf
- Login to the email service
- Send an email with the pdf attached to it
- Profit

## Configuration
- Install [Google Cloud SDK](https://cloud.google.com/sdk/install)
- Create the file `config.py` using `config-example.py` as a model.

## Deployment
This app is deployed to [Google Cloud Functions](https://console.cloud.google.com/functions/):
```shell script
gcloud functions deploy [FUNCTION_NAME] --entry-point main --runtime python37 --trigger-resource [TOPIC_NAME] --trigger-event google.pubsub.topic.publish --timeout 540s
```

Create a pub/sub topic that will trigger the function regularly:
```shell script
gcloud scheduler jobs create pubsub [JOB_NAME] --schedule [SCHEDULE] --topic [TOPIC_NAME] --message-body [MESSAGE_BODY]
```

## More
- Doc about `functions deploy`: https://cloud.google.com/sdk/gcloud/reference/functions/deploy
- For the schedule, see: [cron-job-schedules](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules)

## License
Newspaper delivery is licensed under the MIT License.

Copyright (c) 2020, Daniel Guggenheim
