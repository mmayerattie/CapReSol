# Idealista API - Quick Reference & Integration Guide

## 1. Setup Flow

```
Step 1: Get OAuth Token
  POST /oauth/token
  ↓
Step 2: Use Token to Search Properties
  POST /3.5/{country}/search with Bearer token
  ↓
Step 3: Parse Response & Use Data
```

## 2. Quick Integration Template

```javascript
class IdeallistaAPI {
  constructor(apiKey, secret) {
    this.apiKey = apiKey;
    this.secret = secret;
    this.accessToken = null;
    this.tokenExpiry = null;
  }

  // Step 1: Authenticate
  async authenticate() {
    const credentials = Buffer.from(`${this.apiKey}:${this.secret}`).toString('base64');
    
    const response = await fetch('https://api.idealista.com/oauth/token', {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${credentials}`,
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        grant_type: 'client_credentials',
        scope: 'read'
      })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(`Auth failed: ${data.error_description}`);

    this.accessToken = data.access_token;
    this.tokenExpiry = Date.now() + (data.expires_in * 1000);
    return this.accessToken;
  }

  // Step 2: Search Properties
  async searchProperties(params) {
    // Refresh token if needed
    if (!this.accessToken || Date.now() >= this.tokenExpiry) {
      await this.authenticate();
    }

    const response = await fetch(
      `https://api.idealista.com/3.5/${params.country}/search`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(params)
      }
    );

    const data = await response.json();
    if (!response.ok) throw new Error(`Search failed: ${data.message}`);
    return data;
  }
}

// Usage
const api = new IdeallistaAPI('your_api_key', 'your_secret');
const results = await api.searchProperties({
  country: 'es',
  operation: 'sale',
  propertyType: 'homes',
  center: '40.4168,-3.7038',
  distance: 5000,
  minPrice: 100000,
  maxPrice: 500000,
  bedrooms: '2,3',
  maxItems: 20,
  numPage: 1,
  order: 'price',
  sort: 'asc'
});
```

## 3. Common Search Scenarios

### Scenario A: Find rentals near Madrid city center
```json
{
  "country": "es",
  "operation": "rent",
  "propertyType": "homes",
  "center": "40.4168,-3.7038",
  "distance": 3000,
  "minPrice": 500,
  "maxPrice": 2000,
  "bedrooms": "1,2,3",
  "maxItems": 50,
  "order": "price",
  "sort": "asc"
}
```

### Scenario B: Find investment properties (larger units, good condition)
```json
{
  "country": "es",
  "operation": "sale",
  "propertyType": "homes",
  "locationId": "0-EU-ES-28",
  "minSize": 100,
  "maxSize": 300,
  "preservation": "good",
  "bedrooms": "3,4",
  "bathrooms": "2,3",
  "minPrice": 200000,
  "maxPrice": 800000,
  "maxItems": 50,
  "order": "publicationDate",
  "sort": "desc"
}
```

### Scenario C: Find commercial spaces
```json
{
  "country": "es",
  "operation": "sale",
  "propertyType": "premises",
  "locationId": "0-EU-ES-28",
  "minSize": 100,
  "maxSize": 500,
  "minPrice": 50000,
  "maxPrice": 300000,
  "maxItems": 30,
  "order": "price",
  "sort": "asc"
}
```

### Scenario D: Find new development properties
```json
{
  "country": "es",
  "operation": "sale",
  "propertyType": "homes",
  "center": "40.4168,-3.7038",
  "distance": 5000,
  "newDevelopment": true,
  "bedrooms": "2,3",
  "maxPrice": 600000,
  "order": "publicationDate",
  "sort": "desc",
  "maxItems": 20
}
```

## 4. Important Notes

### Token Management
- Tokens expire in ~12 hours (43199 seconds)
- Always check token expiry before making requests
- Re-authenticate automatically if token is expired

### Rate Limiting
- No explicit rate limits mentioned in documentation
- Implement exponential backoff for retries (optional but recommended)
- Keep requests to reasonable frequency

### Location IDs
- Use `locationId` OR `center` + `distance` (not both)
- `locationId` is more efficient if searching whole regions
- Common Madrid ID: `0-EU-ES-28`

### Bedroom/Bathroom Filters
- Values are comma-separated: `"0,1,2"` or `"1,3"`
- `4` in bedrooms means "4 or more"
- `3` in bathrooms means "3 or more"

### Timestamp Format
- `sinceDate`: Single character codes
  - `W` = Last week
  - `M` = Last month
  - `T` = Last day
  - `Y` = Last 2 days (for sale/rooms)

## 5. Error Handling Checklist

```javascript
// Always handle these errors:
try {
  // 401: Bad credentials or missing auth
  // 400: Invalid parameters
  // 404: Invalid locationId
  // 500: Server error (retry with backoff)
} catch (error) {
  if (error.httpStatus === 401) {
    // Re-authenticate
  } else if (error.httpStatus === 400) {
    // Fix request parameters
  } else if (error.httpStatus === 404) {
    // Verify locationId
  } else if (error.httpStatus === 500) {
    // Retry after delay
  }
}
```

## 6. Response Handling

```javascript
const response = await api.searchProperties({...});

// Key response fields
const {
  actualPage,        // Current page number
  itemsPerPage,      // Results per page
  total,             // Total matching properties
  totalPages,        // Total pages available
  paginable,         // Can paginate results
  summary,           // Human-readable search summary
  elementList        // Array of property objects
} = response;

// Iterate through results
elementList.forEach(property => {
  console.log({
    id: property.propertyCode,
    address: property.address,
    price: property.price,
    size: property.size,
    rooms: property.rooms,
    url: property.url,
    coordinates: [property.latitude, property.longitude],
    images: property.numPhotos,
    hasVideo: property.hasVideo
  });
});

// Handle pagination
if (response.paginable && response.actualPage < response.totalPages) {
  // Fetch next page with numPage: actualPage + 1
}
```

## 7. Property Type Summary

| Type | Use Case | Key Filters |
|------|----------|-------------|
| `homes` | Apartments, houses | bedrooms, bathrooms, size |
| `premises` | Commercial, retail | size, location type |
| `offices` | Office space | size, layout |
| `garages` | Parking, garages | automaticDoor, security |
| `bedrooms` | Room rentals | housemates, smokePolicy |

## 8. Field Mapping for Your Real Estate System

Based on your project structure, map API fields to your database:

```javascript
// API Response → Your Database
const propertyData = {
  // To DEALS table
  address: property.address,
  city: property.municipality,
  country: property.country,
  property_type: property.detailedType.typology,
  size_sqm: property.size,
  bedrooms: property.rooms,
  bathrooms: property.bathrooms,
  asking_price: property.price,
  currency: 'EUR', // Inferred from country
  url: property.url,
  broker_name: 'Idealista',
  
  // To PREDICTIONS table
  // (After ML valuation)
  
  // Geolocation
  latitude: property.latitude,
  longitude: property.longitude
};
```

---

**Pro Tip:** Save these templates as snippets in VS Code for quick reference while developing!
