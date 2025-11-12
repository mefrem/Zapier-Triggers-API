# SQS Module Outputs

output "event_queue_url" {
  description = "Event queue URL"
  value       = aws_sqs_queue.event_queue.url
}

output "event_queue_arn" {
  description = "Event queue ARN"
  value       = aws_sqs_queue.event_queue.arn
}

output "event_queue_name" {
  description = "Event queue name"
  value       = aws_sqs_queue.event_queue.name
}

output "event_dlq_url" {
  description = "Dead letter queue URL"
  value       = aws_sqs_queue.event_dlq.url
}

output "event_dlq_arn" {
  description = "Dead letter queue ARN"
  value       = aws_sqs_queue.event_dlq.arn
}

output "event_dlq_name" {
  description = "Dead letter queue name"
  value       = aws_sqs_queue.event_dlq.name
}
