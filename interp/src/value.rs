//! Signed 64-bit value semantics, matching the Go reference (`littleman/interp`).
//! All arithmetic wraps silently on overflow. Division/modulo are FLOORED, with the
//! remainder taking the divisor's sign — Go's native `/`/`%` truncate toward zero, so
//! the reference implements floored explicitly and so do we.

pub type Val = i64;

#[inline]
pub fn add(a: Val, b: Val) -> Val { a.wrapping_add(b) }
#[inline]
pub fn sub(a: Val, b: Val) -> Val { a.wrapping_sub(b) }
#[inline]
pub fn mul(a: Val, b: Val) -> Val { a.wrapping_mul(b) }
#[inline]
pub fn neg(a: Val) -> Val { a.wrapping_neg() }

/// Floored division. Returns (quotient, remainder) with quotient*b + rem == a and
/// rem taking b's sign. Division by zero: quotient 0, remainder = dividend (a).
#[inline]
pub fn divmod(a: Val, b: Val) -> (Val, Val) {
    if b == 0 {
        return (0, a); // reference: A=0, B keeps the dividend
    }
    let mut q = a.wrapping_div(b);
    let r = a.wrapping_rem(b);
    if r != 0 && ((r < 0) != (b < 0)) {
        q = q.wrapping_sub(1);
        (q, r.wrapping_add(b))
    } else {
        (q, r)
    }
}

/// Floored modulo (result takes b's sign); 0 if b == 0.
#[inline]
pub fn fmod(a: Val, b: Val) -> Val {
    if b == 0 { return 0; }
    let r = a.wrapping_rem(b);
    if r != 0 && ((r < 0) != (b < 0)) { r.wrapping_add(b) } else { r }
}

#[inline]
pub fn and(a: Val, b: Val) -> Val { a & b }
#[inline]
pub fn or(a: Val, b: Val) -> Val { a | b }
#[inline]
pub fn xor(a: Val, b: Val) -> Val { a ^ b }

/// `{` left shift: A << B; 0 if B outside 0..=63.
#[inline]
pub fn shl(a: Val, b: Val) -> Val {
    if (0..=63).contains(&b) { ((a as u64) << (b as u64)) as i64 } else { 0 }
}

/// `}` arithmetic right shift: 0 if B<0; sign-fill if B>63; else A>>B (arithmetic).
#[inline]
pub fn ashr(a: Val, b: Val) -> Val {
    if b < 0 { 0 } else if b > 63 { a >> 63 } else { a >> b }
}

/// `]` backpack halve: arithmetic shift right by 1 (sign-preserving).
#[inline]
pub fn ashr1(a: Val) -> Val { a >> 1 }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn floored_div_matches_spec() {
        assert_eq!(divmod(7, 3), (2, 1));
        assert_eq!(divmod(-7, 3), (-3, 2));   // floored, remainder sign = divisor
        assert_eq!(divmod(7, -3), (-3, -2));
        assert_eq!(divmod(-7, -3), (2, -1));
        assert_eq!(divmod(5, 0), (0, 5));     // div by zero: A=0, B=dividend
        for &(a, b) in &[(7, 3), (-7, 3), (7, -3), (-7, -3), (123, -17)] {
            let (q, r) = divmod(a, b);
            assert_eq!(q.wrapping_mul(b).wrapping_add(r), a);
        }
    }
    #[test]
    fn shifts() {
        assert_eq!(shl(1, 3), 8);
        assert_eq!(shl(1, 64), 0);
        assert_eq!(shl(1, -1), 0);
        assert_eq!(ashr(-8, 1), -4);
        assert_eq!(ashr(-1, 100), -1);
        assert_eq!(ashr(8, -1), 0);
    }
}
