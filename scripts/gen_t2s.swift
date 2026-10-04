// Generate site/t2s.json: a single-character Traditional -> Simplified map,
// taken from ICU's "Traditional-Simplified" transform (ships with macOS).
// Run once on macOS: swift scripts/gen_t2s.swift > site/t2s.json
// Only characters whose conversion is a different single character are kept,
// so search can fold text character by character without changing length.
import Foundation

let transform = StringTransform("Traditional-Simplified")
var map: [String: String] = [:]
// The BMP ideograph blocks, plus planes 2 and 3 whole: every supplementary CJK
// extension (B onwards) lives there, and unassigned code points convert to
// themselves, so they drop out below.
let ranges: [ClosedRange<UInt32>] = [0x3400...0x4DBF, 0x4E00...0x9FFF, 0xF900...0xFAFF, 0x20000...0x3FFFF]
for range in ranges {
    for code in range {
        guard let scalar = Unicode.Scalar(code) else { continue }
        let ch = String(Character(scalar))
        guard let out = ch.applyingTransform(transform, reverse: false),
              out != ch, out.count == 1, out.unicodeScalars.count == 1 else { continue }
        map[ch] = out
    }
}
let data = try JSONSerialization.data(withJSONObject: map, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
