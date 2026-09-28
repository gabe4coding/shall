require_relative "../http/client"

module Partners
  class Sync
    def push(slots)
      connection.put("/slots", slots.to_json)
    end

    private

    def connection
      @connection ||= Http.partner
    end
  end
end
