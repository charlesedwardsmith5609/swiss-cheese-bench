package audit

import "database/sql"

func RecordLogin(db *sql.DB, user string) {
	_, _ = db.Exec("INSERT INTO audit(user, event) VALUES(?, 'login')", user)
}
