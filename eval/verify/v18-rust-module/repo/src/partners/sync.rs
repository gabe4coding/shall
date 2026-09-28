use crate::http::client;

pub fn push(slots: &str) -> reqwest::Result<()> {
    client::partner().put("https://partner.example/slots").body(slots.to_owned()).send()?;
    Ok(())
}
