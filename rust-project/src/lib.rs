use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use ed25519_dalek::{Signer, Verifier};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub from: String,
    pub to: String,
    pub amount: u64,
    pub nonce: u64,
    pub timestamp: u64,
    pub signature: Option<Vec<u8>>,
}

impl Transaction {
    pub fn new(from: String, to: String, amount: u64, nonce: u64) -> Self {
        Self {
            from,
            to,
            amount,
            nonce,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            signature: None,
        }
    }

    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(self.from.as_bytes());
        hasher.update(self.to.as_bytes());
        hasher.update(&self.amount.to_be_bytes());
        hasher.update(&self.nonce.to_be_bytes());
        hasher.update(&self.timestamp.to_be_bytes());
        hasher.finalize().into()
    }

    pub fn sign(&mut self, key: &ed25519_dalek::SigningKey) {
        let hash = self.hash();
        let sig: ed25519_dalek::Signature = key.sign(&hash);
        self.signature = Some(sig.to_bytes().to_vec());
    }

    pub fn verify(&self, public_key: &ed25519_dalek::VerifyingKey) -> bool {
        if let Some(ref sig_bytes) = self.signature {
            if let Ok(sig) = ed25519_dalek::Signature::from_slice(sig_bytes) {
                return public_key.verify(&self.hash(), &sig).is_ok();
            }
        }
        false
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareAttestation {
    pub hardware_id: String,
    pub manufacture_year: u16,
    pub cpu_arch: String,
    pub fingerprint_hash: [u8; 32],
    pub epoch: u64,
    pub signature: Vec<u8>,
}

impl HardwareAttestation {
    pub fn calculate_age_score(&self, current_year: u16) -> f64 {
        let age = current_year.saturating_sub(self.manufacture_year);
        1.0 + (age as f64 * 0.1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transaction_hash_deterministic() {
        let tx1 = Transaction::new("addr1".into(), "addr2".into(), 100, 0);
        let tx2 = Transaction::new("addr1".into(), "addr2".into(), 100, 0);
        assert_eq!(tx1.hash(), tx2.hash());
    }

    #[test]
    fn test_transaction_hash_changes_with_amount() {
        let tx1 = Transaction::new("addr1".into(), "addr2".into(), 100, 0);
        let tx2 = Transaction::new("addr1".into(), "addr2".into(), 200, 0);
        assert_ne!(tx1.hash(), tx2.hash());
    }

    #[test]
    fn test_sign_and_verify() {
        let mut tx = Transaction::new("addr1".into(), "addr2".into(), 100, 0);
        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
        let verifying_key = signing_key.verifying_key();

        tx.sign(&signing_key);
        assert!(tx.verify(&verifying_key));
    }

    #[test]
    fn test_verify_fails_with_wrong_key() {
        let mut tx = Transaction::new("addr1".into(), "addr2".into(), 100, 0);
        let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
        let wrong_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());

        tx.sign(&signing_key);
        assert!(!tx.verify(&wrong_key.verifying_key()));
    }

    #[test]
    fn test_age_score_calculation() {
        let att = HardwareAttestation {
            hardware_id: "hw-001".into(),
            manufacture_year: 1995,
            cpu_arch: "x86".into(),
            fingerprint_hash: [0u8; 32],
            epoch: 1,
            signature: vec![],
        };
        let score = att.calculate_age_score(2026);
        assert!((score - 4.1).abs() < 0.01);
    }
}
