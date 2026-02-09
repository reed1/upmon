use serde::Deserialize;

#[derive(Deserialize)]
pub struct Env {
    pub database_url: String,
}

impl Env {
    pub fn load() -> Self {
        dotenvy::from_filename(".env.local").ok();
        dotenvy::from_filename(".env").ok();
        envy::from_env().expect("failed to parse environment variables")
    }
}
