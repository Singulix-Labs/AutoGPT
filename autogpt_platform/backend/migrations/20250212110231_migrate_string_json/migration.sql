CREATE OR REPLACE FUNCTION migrate_text_column_to_json(
    p_schema text,  -- Schema name, e.g. 'platform'
    p_table  text,  -- Table name, e.g. 'AgentNodeExecution'
    p_col    text   -- Column name to convert, e.g. 'executionData'
) RETURNS void AS $$
DECLARE
    full_table text;
    tmp_col    text;
BEGIN
    -- Build the fully qualified table name.
    full_table := format('%I.%I', p_schema, p_table);
    -- Construct the temporary column name.
    tmp_col := p_col || '_tmp';

    -- 1. Add a temporary column of type JSON.
    EXECUTE format('ALTER TABLE %s ADD COLUMN %I json;', full_table, tmp_col);

    -- 2. Update all rows:
    --    If the original value is NULL, use an empty JSON object.
    --    Otherwise, cast the value to JSON (which will raise an exception if invalid).
    EXECUTE format(
        'UPDATE %s SET %I = CASE WHEN %I IS NULL THEN ''{}''::json ELSE %I::json END;',
         full_table, tmp_col, p_col, p_col
    );

    -- 3. Drop the original text column.
    EXECUTE format('ALTER TABLE %s DROP COLUMN %I;', full_table, p_col);

    -- 4. Rename the temporary column to the original column name.
    EXECUTE format('ALTER TABLE %s RENAME COLUMN %I TO %I;', full_table, tmp_col, p_col);
END;
$$ LANGUAGE plpgsql;


BEGIN;
  SELECT migrate_text_column_to_json('platform', 'AgentGraphExecution', 'stats');
  SELECT migrate_text_column_to_json('platform', 'AgentNodeExecution', 'stats');
  SELECT migrate_text_column_to_json('platform', 'AgentNodeExecution', 'executionData');
  SELECT migrate_text_column_to_json('platform', 'AgentNode', 'constantInput');
  SELECT migrate_text_column_to_json('platform', 'AgentNode', 'metadata');
  SELECT migrate_text_column_to_json('platform', 'AgentNodeExecutionInputOutput', 'data');
COMMIT;
