-- Some Supabase setups have comments.post_text NOT NULL without a default.

alter table comments add column if not exists post_text text;

update comments
set post_text = coalesce(post_text, generated_comment, sent_comment, '')
where post_text is null;
