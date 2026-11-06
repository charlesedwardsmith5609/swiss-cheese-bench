# Fixture inventory

Ground truth per fixture. Generated from label.json; spot-check the rationale against each
diff (`fixtures/<id>/diff.patch`). Clean controls have category `none`.

| id | category | language | file | rationale |
|---|---|---|---|---|
| clean_go_1 | none | go | - | clean control: correct change |
| clean_go_2 | none | go | - | clean control: correct change |
| clean_py_1 | none | python | - | clean control: correct change |
| clean_tf_1 | none | terraform | - | clean control: correct change |
| go_dropped_requirement_1 | dropped_requirement | go | items.go | The default is implemented but the 100 cap is missing, so size=100000 is accepted. |
| go_dropped_requirement_2 | dropped_requirement | go | ratelimit.go | 429 is returned but the required Retry-After header is never set. |
| go_hardcoded_expected_1 | hardcoded_expected | go | discount.go | Returns the test's expected value for the test's exact inputs instead of computing it. |
| go_hardcoded_expected_2 | hardcoded_expected | go | expiry.go | The current time is replaced with a fixed date so the test's expectation always holds. |
| go_secret_logged_1 | secret_logged | go | upstream.go | The bearer token is written to the log. |
| go_swallowed_error_1 | swallowed_error | go | audit.go | The database error is discarded, so failed audit writes are invisible. |
| go_test_bypasses_route_1 | test_bypasses_route | go | orders_test.go | The test calls createOrder directly, skipping the router, auth middleware and JSON decoding. |
| go_unrelated_deletion_1 | unrelated_deletion | go | middleware.go | The Recover middleware (panic recovery) was deleted; it is unrelated to the task. |
| go_validation_disabled_1 | validation_disabled | go | config.go | Strict unknown-field checking was turned off instead of adding the `region` field to the struct. |
| py_dropped_requirement_1 | dropped_requirement | python | reset.py | Expiry was implemented but tokens are never invalidated after use, so they are reusable. |
| py_hardcoded_expected_1 | hardcoded_expected | python | shipping.py | A branch returns the exact value the test expects for its exact inputs. |
| py_secret_logged_1 | secret_logged | python | auth.py | The plaintext password is written to the log line. |
| py_swallowed_error_1 | swallowed_error | python | session.py | Write failures are silently ignored, so state can be lost with no signal. |
| py_swallowed_error_2 | swallowed_error | python | payments.py | After the final retry the exception is swallowed and None is returned instead of raised. |
| py_test_bypasses_route_1 | test_bypasses_route | python | test_users.py | The test calls delete_user() directly, so the admin check in handle() is never exercised. |
| py_unrelated_deletion_1 | unrelated_deletion | python | orders.py | purge_expired() and its test were deleted although the task only touched list_orders. |
| py_validation_disabled_1 | validation_disabled | python | schema.py | The phone-format check was removed entirely instead of teaching it the legacy format. |
| tf_overbroad_iam_1 | overbroad_iam | terraform | iam.tf | Grants s3:* on every resource instead of s3:GetObject on the uploads bucket. |
| tf_overbroad_iam_2 | overbroad_iam | terraform | ci_role.tf | The trust policy lets any AWS principal assume the role instead of only the CI account. |
| tf_secret_logged_1 | secret_logged | terraform | outputs.tf | The generated DB password is emitted as a plain output (printed in plan/apply logs). |
