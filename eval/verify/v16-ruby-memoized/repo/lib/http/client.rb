require "faraday"

module Http
  def self.partner
    Faraday.new(url: "https://partner.example") do |f|
      f.options.timeout = 3
      f.options.open_timeout = 1
    end
  end
end
