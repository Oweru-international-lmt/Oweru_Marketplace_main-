from django.db import migrations


SQL = r"""
CREATE FUNCTION marketplace_rate_table_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE invalid boolean;
BEGIN
  IF OLD.published_at IS NOT NULL THEN
    RAISE EXCEPTION 'Published rate versions are immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  IF NEW.published_at IS NOT NULL THEN
    SELECT NOT EXISTS (SELECT 1 FROM commissions_rateband WHERE table_id=NEW.id)
      OR EXISTS (SELECT 1 FROM commissions_rateband WHERE table_id=NEW.id AND oweru_rate+agent_rate<>NEW.total_rate)
      OR (SELECT min(lower) FROM commissions_rateband WHERE table_id=NEW.id)<>0
      OR (SELECT count(*) FROM commissions_rateband WHERE table_id=NEW.id AND upper IS NULL)<>1
      OR EXISTS (
        SELECT 1 FROM (
          SELECT lower, lag(upper) OVER (ORDER BY lower) AS previous_upper,
                 row_number() OVER (ORDER BY lower) AS position
          FROM commissions_rateband WHERE table_id=NEW.id
        ) b WHERE position>1 AND (previous_upper IS NULL OR lower<>previous_upper+1)
      ) INTO invalid;
    IF invalid THEN RAISE EXCEPTION 'Published bands require continuous coverage and reconciled rates'; END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER marketplace_rate_table_guard BEFORE UPDATE OR DELETE ON commissions_ratetable
FOR EACH ROW EXECUTE FUNCTION marketplace_rate_table_guard();

CREATE FUNCTION marketplace_rate_band_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE publication timestamptz;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    SELECT published_at INTO publication FROM commissions_ratetable WHERE id=OLD.table_id FOR UPDATE;
    IF publication IS NOT NULL THEN RAISE EXCEPTION 'Published bands are immutable'; END IF;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT published_at INTO publication FROM commissions_ratetable WHERE id=NEW.table_id FOR UPDATE;
    IF publication IS NOT NULL THEN RAISE EXCEPTION 'Published bands are immutable'; END IF;
    RETURN NEW;
  END IF;
  RETURN OLD;
END $$;
CREATE TRIGGER marketplace_rate_band_guard BEFORE INSERT OR UPDATE OR DELETE ON commissions_rateband
FOR EACH ROW EXECUTE FUNCTION marketplace_rate_band_guard();

CREATE FUNCTION marketplace_listing_rate_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.rate_table_id IS DISTINCT FROM NEW.rate_table_id THEN
    RAISE EXCEPTION 'Listing rate version freezes at creation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER marketplace_listing_rate_guard BEFORE UPDATE ON listings_listing
FOR EACH ROW EXECUTE FUNCTION marketplace_listing_rate_guard();

CREATE FUNCTION marketplace_deal_finance_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.owner_bank_snapshot IS DISTINCT FROM OLD.owner_bank_snapshot OR
     NEW.oweru_bank_snapshot IS DISTINCT FROM OLD.oweru_bank_snapshot THEN
    RAISE EXCEPTION 'Deal receiving bank snapshots are immutable';
  END IF;
  IF ROW(NEW.owner_price, NEW.final_selling_price, NEW.rate_table_id, NEW.rate_band_id,
         NEW.total_rate, NEW.oweru_rate, NEW.buyer_to_owner, NEW.buyer_to_oweru,
         NEW.oweru_keeps, NEW.agent_payout) IS DISTINCT FROM
     ROW(OLD.owner_price, OLD.final_selling_price, OLD.rate_table_id, OLD.rate_band_id,
         OLD.total_rate, OLD.oweru_rate, OLD.buyer_to_owner, OLD.buyer_to_oweru,
         OLD.oweru_keeps, OLD.agent_payout) THEN
    IF OLD.state<>'OPEN' OR NEW.final_selling_price=OLD.final_selling_price
       OR EXISTS(SELECT 1 FROM payments_paymentproof WHERE deal_id=OLD.id)
       OR EXISTS(SELECT 1 FROM payments_paymentconfirmation WHERE deal_id=OLD.id)
       OR EXISTS(SELECT 1 FROM payments_officialtaxreceipt WHERE deal_id=OLD.id)
       OR OLD.agreement_id IS NOT NULL THEN
      RAISE EXCEPTION 'Deal financial breakdown is frozen';
    END IF;
    IF NEW.rate_table_id<>OLD.rate_table_id THEN RAISE EXCEPTION 'Deal rate version is immutable'; END IF;
  END IF;
  IF OLD.state='COMPLETE' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'Completed Deals are immutable';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER marketplace_deal_finance_guard BEFORE UPDATE ON deals_deal
FOR EACH ROW EXECUTE FUNCTION marketplace_deal_finance_guard();

CREATE FUNCTION marketplace_payout_amount_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.amount<>(SELECT agent_payout FROM deals_deal WHERE id=NEW.deal_id) THEN
    RAISE EXCEPTION 'Payout amount must equal frozen Deal payout';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER marketplace_payout_amount_guard BEFORE INSERT OR UPDATE ON payments_payout
FOR EACH ROW EXECUTE FUNCTION marketplace_payout_amount_guard();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for name, table in [
        ("rate_table", "commissions_ratetable"), ("rate_band", "commissions_rateband"),
        ("listing_rate", "listings_listing"), ("deal_finance", "deals_deal"),
        ("payout_amount", "payments_payout"),
    ]:
        schema_editor.execute(f"DROP TRIGGER marketplace_{name}_guard ON {table}")
        schema_editor.execute(f"DROP FUNCTION marketplace_{name}_guard()")


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial"), ("deals", "0003_deal_bank_snapshots")]
    operations = [migrations.RunPython(install, uninstall)]
