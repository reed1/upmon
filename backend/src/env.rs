use serde::Deserialize;

fn default_api_port() -> u16 {
    3000
}

#[derive(Deserialize)]
pub struct Env {
    pub database_url: String,
    pub api_key: String,
    #[serde(default = "default_api_port")]
    pub api_port: u16,
}

impl Env {
    pub fn load() -> Self {
        dotenvy::from_filename(".env.local").ok();
        dotenvy::from_filename(".env").ok();
        envy::from_env().expect("failed to parse environment variables")
    }
}
