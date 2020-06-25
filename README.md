# Send daily newspaper
Send an email each morning with the newspaper of the day in pdf.

## Configuration
- Install [Google Cloud SDK](https://cloud.google.com/sdk/install)
- Create the file `config.py` using `config-example.py` as a model.

## Deploy to Google Cloud Functions
Deploy to [Cloud Functions](https://console.cloud.google.com/functions/):
```shell script
gcloud functions deploy [FUNCTION_NAME] --entry-point main --runtime python37 --trigger-resource [TOPIC_NAME] --trigger-event google.pubsub.topic.publish --timeout 540s
```

Create a pub/sub topic that will trigger the function regularly:
```shell script
gcloud scheduler jobs create pubsub [JOB_NAME] --schedule [SCHEDULE] --topic [TOPIC_NAME] --message-body [MESSAGE_BODY]
```

### More
- Doc about `functions deploy`: https://cloud.google.com/sdk/gcloud/reference/functions/deploy
- For the schedule, see: [cron-job-schedules](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules)