// Thematic groupings for browsing, layered on top of the frequency-ordered
// lesson path. Computed client-side from each vocab item's existing English
// gloss(es) -- no new data file, no change to lesson order or scheduling.
// A word can land in more than one category; that's fine, it's just a study
// shortcut for finding common nouns (e.g. "maison") without waiting for the
// frequency path to reach them.

export const CATEGORIES = [
  {
    name: "House & Home",
    keywords: ["house", "home", "room", "door", "window", "roof", "kitchen", "bedroom",
      "bathroom", "garden", "wall", "floor", "ceiling", "key", "furniture", "table",
      "chair", "bed", "lamp", "curtain", "mirror", "shelf", "stairs", "garage", "yard",
      "fence", "chimney", "attic", "cellar", "apartment"],
  },
  {
    name: "Family & People",
    keywords: ["mother", "father", "parent", "brother", "sister", "son", "daughter",
      "child", "children", "baby", "husband", "wife", "grandmother", "grandfather",
      "uncle", "aunt", "cousin", "family", "friend", "man", "woman", "boy", "girl",
      "people", "person", "neighbor"],
  },
  {
    name: "Food & Drink",
    keywords: ["food", "eat", "drink", "bread", "cheese", "meat", "fish", "chicken",
      "egg", "milk", "water", "wine", "coffee", "tea", "fruit", "apple", "vegetable",
      "potato", "rice", "sugar", "salt", "butter", "soup", "cake", "cook", "meal",
      "breakfast", "lunch", "dinner", "restaurant", "plate", "beer", "juice"],
  },
  {
    name: "Animals",
    keywords: ["dog", "cat", "horse", "cow", "pig", "bird", "fish", "sheep", "goat",
      "chicken", "duck", "mouse", "rabbit", "lion", "tiger", "bear", "wolf", "fox",
      "animal", "insect", "bee", "fly", "butterfly", "snake"],
  },
  {
    name: "Body & Health",
    keywords: ["head", "hand", "arm", "leg", "foot", "eye", "ear", "nose", "mouth",
      "hair", "face", "back", "heart", "body", "blood", "bone", "skin", "tooth",
      "teeth", "finger", "knee", "shoulder", "stomach", "health", "sick", "ill",
      "pain", "doctor", "hospital", "medicine"],
  },
  {
    name: "Clothing",
    keywords: ["shirt", "dress", "pants", "shoe", "shoes", "coat", "hat", "jacket",
      "skirt", "sock", "socks", "glove", "clothing", "clothes", "scarf", "belt"],
  },
  {
    name: "Colors",
    keywords: ["red", "blue", "green", "yellow", "black", "white", "gray", "grey",
      "brown", "pink", "purple", "orange", "color"],
  },
  {
    name: "Time & Calendar",
    keywords: ["day", "week", "month", "year", "hour", "minute", "second", "morning",
      "evening", "night", "today", "tomorrow", "yesterday", "monday", "tuesday",
      "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
      "march", "april", "may", "june", "july", "august", "september", "october",
      "november", "december", "spring", "summer", "autumn", "winter", "season",
      "clock", "time"],
  },
  {
    name: "Weather & Nature",
    keywords: ["weather", "rain", "snow", "sun", "wind", "cloud", "storm", "sky",
      "tree", "forest", "mountain", "river", "lake", "sea", "ocean", "beach", "stone",
      "rock", "flower", "grass", "leaf", "earth", "world", "nature", "cold", "hot",
      "warm"],
  },
  {
    name: "Travel & Places",
    keywords: ["city", "town", "street", "road", "country", "village", "travel",
      "train", "car", "bus", "plane", "airport", "station", "ticket", "map", "hotel",
      "bridge", "border"],
  },
  {
    name: "Work & School",
    keywords: ["work", "job", "school", "teacher", "student", "book", "class",
      "office", "company", "business", "money", "pay", "salary", "meeting", "project",
      "computer", "paper", "pen", "pencil", "exam", "university", "lesson"],
  },
  {
    name: "Emotions & Feelings",
    keywords: ["happy", "sad", "angry", "afraid", "fear", "love", "hate", "joy",
      "worry", "proud", "ashamed", "surprised", "tired", "bored", "excited",
      "nervous", "calm", "feeling"],
  },
];

function wordsOf(text) {
  return text.toLowerCase().match(/[a-zàâäéèêëïîôöùûüç']+/g) || [];
}

// Groups the vocab items in `bank` by category. Returns an array of
// { name, itemIds: Set<string>, count }, sorted by size, categories with no
// matches omitted.
export function buildCategoryGroups(bank) {
  const groups = CATEGORIES.map((cat) => ({
    name: cat.name,
    keywords: new Set(cat.keywords),
    itemIds: new Set(),
  }));

  for (const item of bank) {
    if (item.type !== "vocab") continue;
    const glossWords = new Set();
    for (const g of item.gloss) {
      for (const w of wordsOf(g)) glossWords.add(w);
    }
    for (const group of groups) {
      for (const kw of group.keywords) {
        if (glossWords.has(kw)) {
          group.itemIds.add(item.id);
          break;
        }
      }
    }
  }

  return groups
    .map(({ name, itemIds }) => ({ name, itemIds, count: itemIds.size }))
    .filter((g) => g.count > 0)
    .sort((a, b) => b.count - a.count);
}
