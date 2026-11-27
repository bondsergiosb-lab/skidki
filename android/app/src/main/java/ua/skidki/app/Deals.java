package ua.skidki.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Отбор горящих скидок для профиля — те же правила, что в app.js (passes / sizeMatch),
 * только без поиска и выбранной категории: фильтры профиля, затем «больше всего интересует»
 * и любимые бренды первыми, внутри — от самой большой реальной скидки.
 */
final class Deals {
    private static final Set<String> SUSPICIOUS = new HashSet<>(Arrays.asList("infl", "perm", "huge"));
    private static final Pattern SPLIT = Pattern.compile("[^0-9A-ZА-ЯІЇЄҐ.]+");
    private static final Pattern MONTHS = Pattern.compile("\\d\\s*(м|мес|m)(?![a-zа-яіїєґ])",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    private static final Pattern RANGE = Pattern.compile("(\\d+(?:[.,]\\d+)?)\\s*[-–]\\s*(\\d+(?:[.,]\\d+)?)");
    private static final Pattern NUMBER = Pattern.compile("^\\d+(\\.\\d+)?$");

    private Deals() {
    }

    static List<JSONObject> pick(JSONArray items, JSONObject p, Map<String, Double> sent, int limit) {
        Set<String> audience = set(p.optJSONArray("audience"));
        Set<String> stores = set(p.optJSONArray("stores"));
        Set<String> cats = set(p.optJSONArray("cats"));
        Set<String> subsFav = set(p.optJSONArray("subsFav"));
        Set<String> brandsFav = new HashSet<>(list(p.optString("brandsFav")));
        Set<String> brandsHide = new HashSet<>(list(p.optString("brandsHide")));
        int minDiscount = p.optInt("minDiscount", 30);
        double maxPrice = p.optDouble("maxPrice", 0);
        boolean hideSuspicious = p.optBoolean("hideSuspicious", true);
        boolean onlySize = p.optBoolean("onlySize", false);

        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject it = items.optJSONObject(i);
            if (it == null) continue;
            String id = it.optString("id");
            double price = it.optDouble("p", 0);
            if (!audience.isEmpty() && !audience.contains(it.optString("a"))) continue;
            if (!stores.isEmpty() && !stores.contains(it.optString("s"))) continue;
            if (!cats.isEmpty() && !cats.contains(it.optString("c"))) continue;
            if (it.optInt("r") < minDiscount) continue;
            if (maxPrice > 0 && price > maxPrice) continue;
            if (hideSuspicious && hasAny(it.optJSONArray("f"), SUSPICIOUS)) continue;
            String brand = it.optString("b").toLowerCase(Locale.ROOT);
            if (brandsHide.contains(brand)) continue;
            if (onlySize && Boolean.FALSE.equals(fits(it, p))) continue;
            Double was = sent.get(id);
            if (was != null && price >= was) continue;  // уже присылали и не подешевело
            out.add(it);
        }
        out.sort((a, b) -> {
            int pa = priority(a, subsFav, brandsFav), pb = priority(b, subsFav, brandsFav);
            if (pa != pb) return pb - pa;
            if (a.optInt("r") != b.optInt("r")) return b.optInt("r") - a.optInt("r");
            return Double.compare(b.optDouble("k", 0), a.optDouble("k", 0));
        });
        return out.subList(0, Math.min(limit, out.size()));
    }

    /** Какие части данных нужны профилю (как SHARD_OF в app.js): w — женское и унисекс, m — мужское, k — детское. */
    static List<String> shards(JSONObject p) {
        Set<String> audience = set(p.optJSONArray("audience"));
        List<String> out = new ArrayList<>();
        if (audience.isEmpty()) return Arrays.asList("w", "m", "k");
        // унисекс лежит и в женской, и в мужской части
        if (audience.contains("women") || (audience.contains("unisex") && !audience.contains("men"))) out.add("w");
        if (audience.contains("men")) out.add("m");
        if (audience.contains("girls") || audience.contains("boys") || audience.contains("kids")) out.add("k");
        return out;
    }

    private static int priority(JSONObject it, Set<String> subsFav, Set<String> brandsFav) {
        return (subsFav.contains(it.optString("sc")) || brandsFav.contains(it.optString("b").toLowerCase(Locale.ROOT))) ? 1 : 0;
    }

    /** true — размер есть, false — нет, null — неизвестно. */
    private static Boolean fits(JSONObject it, JSONObject p) {
        String c = it.optString("c");
        List<String> wanted = new ArrayList<>();
        if ("shoes".equals(c)) wanted = list(p.optString("shoeSizes"));
        else if ("clothes".equals(c)) wanted = list(p.optString("sizes"));
        JSONArray z = it.optJSONArray("z");
        if (wanted.isEmpty() || z == null || z.length() == 0) return null;
        for (int i = 0; i < wanted.size(); i++) wanted.set(i, wanted.get(i).toUpperCase(Locale.ROOT).replace(',', '.'));
        for (int i = 0; i < z.length(); i++) {
            String s = z.optString(i);
            List<String> toks = Arrays.asList(SPLIT.split(s.toUpperCase(Locale.ROOT).replace(',', '.')));
            Matcher range = MONTHS.matcher(s).find() ? null : RANGE.matcher(s);
            boolean hasRange = range != null && range.find();
            for (String w : wanted) {
                if (toks.contains(w)) return true;
                if (hasRange && NUMBER.matcher(w).matches()) {
                    double a = Double.parseDouble(range.group(1).replace(',', '.'));
                    double b = Double.parseDouble(range.group(2).replace(',', '.'));
                    double x = Double.parseDouble(w);
                    if (a < b && b - a <= 20 && x >= a && x <= b) return true;
                }
            }
        }
        return false;
    }

    private static boolean hasAny(JSONArray arr, Set<String> values) {
        if (arr == null) return false;
        for (int i = 0; i < arr.length(); i++) if (values.contains(arr.optString(i))) return true;
        return false;
    }

    private static Set<String> set(JSONArray arr) {
        Set<String> s = new HashSet<>();
        if (arr != null) for (int i = 0; i < arr.length(); i++) s.add(arr.optString(i));
        return s;
    }

    static List<String> list(String csv) {
        List<String> out = new ArrayList<>();
        for (String x : csv.split(",")) {
            String t = x.trim().toLowerCase(Locale.ROOT);
            if (!t.isEmpty()) out.add(t);
        }
        return out;
    }
}
