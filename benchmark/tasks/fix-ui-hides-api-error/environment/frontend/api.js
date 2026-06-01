/**
 * Frontend API client for user profiles.
 */
async function fetchUserProfile(userId) {
    const response = await fetch(`/api/user/${userId}`);
    const data = await response.json();
    return data;
}

module.exports = { fetchUserProfile };
