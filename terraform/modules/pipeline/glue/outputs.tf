output "database_name" {
  description = "Name of the Glue catalog database"
  value       = aws_glue_catalog_database.main.name
}

output "bronze_statcast_table_name" {
  description = "Name of the bronze statcast Glue table"
  value       = aws_glue_catalog_table.bronze_statcast.name
}
