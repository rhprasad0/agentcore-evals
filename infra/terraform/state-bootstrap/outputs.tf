output "state_bucket_name" {
  description = "Use locally as the partial S3 backend bucket value; do not commit the resolved name."
  value       = aws_s3_bucket.terraform_state.id
}
