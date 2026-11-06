output "db_host" {
  value = aws_db_instance.main.address
}

output "db_user" {
  value = aws_db_instance.main.username
}

output "db_password" {
  value = random_password.db.result
}
