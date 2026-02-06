# Issues - Melody Extraction Pivot

## 2026-02-06: Pop2Piano SSL Certificate Error

**Task**: Task 1 - 기존 기능 로컬 실행 확인

**Error**:
```
'[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

**Root Cause**: 
- Corporate network proxy/firewall with self-signed SSL certificate
- HuggingFace model download fails due to SSL verification

**Impact**: 
- Pop2Piano cannot be loaded locally without SSL workaround
- NOT a blocker for the main goal (replacing Pop2Piano)

**Decision**: 
- Skip Task 1 (Pop2Piano verification)
- Proceed directly to spike tasks (2, 3, 4) which test alternative models
- Pop2Piano will be replaced anyway, so this issue becomes irrelevant

**Workaround (if needed later)**:
```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```
Or set environment variable: `CURL_CA_BUNDLE=""`

---
