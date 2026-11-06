variable "ci_account_id" {
  type = string
}

resource "aws_iam_role" "ci_deploy" {
  name = "ci-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { AWS = "*" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ci_ecs" {
  role       = aws_iam_role.ci_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonECS_FullAccess"
}
