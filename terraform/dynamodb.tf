# --- DynamoDB Tables (Mock Salesforce Data Store) ---

resource "aws_dynamodb_table" "vlocity_error_logs" {
  name         = var.vlocity_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "Id"

  attribute {
    name = "Id"
    type = "S"
  }

  attribute {
    name = "User"
    type = "S"
  }

  attribute {
    name = "Datetime"
    type = "S"
  }

  global_secondary_index {
    name            = "User-Datetime-index"
    hash_key        = "User"
    range_key       = "Datetime"
    projection_type = "ALL"
  }
}

resource "aws_dynamodb_table" "ps_exception_logs" {
  name         = var.exception_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "Id"

  attribute {
    name = "Id"
    type = "S"
  }
}

# --- Seed Mock Data ---

resource "null_resource" "seed_vlocity_logs" {
  depends_on = [aws_dynamodb_table.vlocity_error_logs]

  provisioner "local-exec" {
    command = <<-EOT
      python3 -c "
import json, boto3
table = boto3.resource('dynamodb', region_name='${var.aws_region}').Table('${var.vlocity_table_name}')
with open('../mock_data/vlocity_error_logs.json') as f:
    items = json.load(f)
with table.batch_writer() as batch:
    for item in items:
        batch.put_item(Item=item)
print(f'Seeded {len(items)} Vlocity Error Logs')
"
    EOT
  }

  triggers = {
    data_hash = filemd5("${path.module}/../mock_data/vlocity_error_logs.json")
  }
}

resource "null_resource" "seed_exception_logs" {
  depends_on = [aws_dynamodb_table.ps_exception_logs]

  provisioner "local-exec" {
    command = <<-EOT
      python3 -c "
import json, boto3
table = boto3.resource('dynamodb', region_name='${var.aws_region}').Table('${var.exception_table_name}')
with open('../mock_data/ps_exception_logs.json') as f:
    items = json.load(f)
with table.batch_writer() as batch:
    for item in items:
        batch.put_item(Item=item)
print(f'Seeded {len(items)} PS Exception Logs')
"
    EOT
  }

  triggers = {
    data_hash = filemd5("${path.module}/../mock_data/ps_exception_logs.json")
  }
}
