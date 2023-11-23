# voulezvousvoucher
Voulez vous voucher avec moi?



# Upgrade existing sqlite3

```sql
ALTER TABLE users ADD COLUMN num_bought INTEGER NOT NULL DEFAULT 0;
```