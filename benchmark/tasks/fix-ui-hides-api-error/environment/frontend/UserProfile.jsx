import React, { useState, useEffect } from 'react';
import { fetchUserProfile } from './api';
import { classifyProfileResponse } from './profile_state';

function UserProfile({ userId }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        setLoading(true);
        setError(null);
        fetchUserProfile(userId)
            .then(data => {
                const viewState = classifyProfileResponse(data);
                setUser(viewState.user);
                setError(viewState.error);
                setLoading(false);
            })
            .catch(err => {
                setError(err.message);
                setLoading(false);
            });
    }, [userId]);

    if (loading) return <div className="spinner">Loading...</div>;

    // Shows "No data available" for BOTH "no user" AND "server error" cases
    if (!user) return <div className="no-data">No data available</div>;

    return (
        <div className="user-profile">
            <h1>{user.name}</h1>
            <p>{user.email}</p>
            <span className="role">{user.role}</span>
        </div>
    );
}

export default UserProfile;
